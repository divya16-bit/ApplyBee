import asyncio
import os
import random
from datetime import datetime
from loguru import logger
from playwright.async_api import async_playwright
from concurrency_limit import playwright_semaphore 
from dotenv import load_dotenv


try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


# --- Helper: best match finder between form label and gist/resume keys ---
def find_best_answer(field_label: str, gist: dict, resume: dict) -> str:
    """Finds the most relevant answer from gist or resume based on field label."""
    field_label_l = (field_label or "").lower()

    # 1️⃣ Try exact / substring match in gist
    for key, val in gist.items():
        if not val:
            continue
        kl = key.lower()
        if kl in field_label_l or field_label_l in kl:
            return str(val)

    # 2️⃣ Try fuzzy match in gist
    if fuzz:
        best_key, best_score = None, 0
        for k in gist.keys():
            score = fuzz.partial_ratio(field_label_l, k.lower())
            if score > best_score:
                best_key, best_score = k, score
        if best_key and best_score >= 70:
            return str(gist[best_key])

    # 3️⃣ Fallback to resume data
    if fuzz:
        best_key, best_score = None, 0
        for k in resume.keys():
            score = fuzz.partial_ratio(field_label_l, k.lower())
            if score > best_score:
                best_key, best_score = k, score
        if best_key and best_score >= 65:
            return str(resume[best_key])
    else:
        for k, v in resume.items():
            if k.lower() in field_label_l or field_label_l in k.lower():
                return str(v)

    return ""


def _escape_for_xpath(s: str) -> str:
    """Escape single quote in xpath literal by using concat()."""
    if "'" not in s:
        return f"'{s}'"
    parts = s.split("'")
    concat_parts = []
    for i, p in enumerate(parts):
        if p:
            concat_parts.append(f"'{p}'")
        if i != len(parts) - 1:
            concat_parts.append('"\'"')
    return "concat(" + ", ".join(concat_parts) + ")"


def _css_escape(s: str) -> str:
    """Minimal CSS escape for attribute selectors."""
    return s.replace("\n", " ").replace("'", "").replace('"', "").strip()


def _match_answer_to_option(answer: str, options: list) -> str:
    """
    Smart matching of answer to available options.
    Returns the best matching option or None.
    """
    if not answer or not options:
        return None
    
    answer_lower = answer.lower().strip()
    
    # 1. Exact match (case-insensitive)
    for opt in options:
        if opt.lower().strip() == answer_lower:
            logger.debug(f"✅ Exact match: '{opt}'")
            return opt
    
    # 2. Partial match (answer in option or option in answer)
    for opt in options:
        opt_lower = opt.lower().strip()
        if answer_lower in opt_lower or opt_lower in answer_lower:
            logger.debug(f"✅ Partial match: '{opt}'")
            return opt
    
    # 3. Special case: Yes/No questions
    if answer_lower in ['yes', 'y', 'true', '1']:
        for opt in options:
            if opt.lower().strip() in ['yes', 'y']:
                logger.debug(f"✅ Yes/No match: '{opt}'")
                return opt
    
    if answer_lower in ['no', 'n', 'false', '0']:
        for opt in options:
            if opt.lower().strip() in ['no', 'n']:
                logger.debug(f"✅ Yes/No match: '{opt}'")
                return opt
    
    # 4. Fuzzy match if available
    if fuzz:
        best_match = None
        best_score = 0
        for opt in options:
            score = fuzz.ratio(answer_lower, opt.lower())
            if score > best_score:
                best_match = opt
                best_score = score
        
        if best_score >= 70:  # 70% similarity threshold
            logger.debug(f"✅ Fuzzy match: '{answer}' → '{best_match}' (score: {best_score})")
            return best_match
    
    # 5. First word match (for longer answers)
    answer_first_word = answer_lower.split()[0] if answer_lower.split() else ""
    if answer_first_word:
        for opt in options:
            if answer_first_word in opt.lower():
                logger.debug(f"✅ First word match: '{opt}'")
                return opt
    
    # 6. Number extraction (e.g., "5 years" from "5")
    import re
    answer_numbers = re.findall(r'\d+', answer)
    if answer_numbers:
        for num in answer_numbers:
            for opt in options:
                if num in opt:
                    logger.debug(f"✅ Number match: '{opt}'")
                    return opt
    
    return None


async def _keyboard_select_fallback(control_element, answer: str) -> bool:
    """
    Fallback: Use keyboard navigation to select option.
    Useful when options are not directly clickable.
    """
    try:
        logger.info("🎹 Trying keyboard navigation fallback")
        
        # Focus on the control
        await control_element.click()
        await asyncio.sleep(0.3)
        
        # Type the answer (React-Select often filters on typing)
        answer_clean = answer.strip()[:50]  # Limit length
        await control_element.press_sequentially(answer_clean, delay=50)
        await asyncio.sleep(0.5)
        
        # Press Enter to select first filtered option
        await control_element.press("Enter")
        await asyncio.sleep(0.3)
        
        logger.info("✅ Keyboard selection attempted")
        return True
        
    except Exception as e:
        logger.debug(f"Keyboard fallback failed: {e}")
        return False


# --- NEW: Enhanced Greenhouse Dropdown Handler ---
async def safe_fill_greenhouse_dropdown(frame, question_label: str, answer: str) -> bool:
    """
    Handles Greenhouse React-Select dropdowns specifically.
    Supports multiple strategies to find and fill the dropdown.
    """
    try:
        if not answer:
            logger.debug("No answer provided for dropdown")
            return False

        logger.info(f"🔍 Looking for dropdown: '{question_label}' → Answer: '{answer}'")
        
        # Strategy 1: Find by label text
        label_text_lower = question_label.lower().strip()
        
        # Find all select containers
        all_selects = await frame.locator("div.select__container").all()
        logger.debug(f"Found {len(all_selects)} select containers")
        
        for select_container in all_selects:
            try:
                # Get the label for this dropdown
                label = select_container.locator("label.select__label")
                if await label.count() == 0:
                    continue
                    
                label_full_text = await label.inner_text()
                label_clean = label_full_text.replace('*', '').strip()
                logger.debug(f"Checking dropdown with label: '{label_clean}'")
                
                # Check if this is the dropdown we're looking for
                if not (label_text_lower in label_clean.lower() or 
                        label_clean.lower() in label_text_lower):
                    continue
                
                logger.info(f"✅ Found matching dropdown: '{label_clean}'")
                
                # Check if already filled
                has_value = await select_container.locator("div.select__single-value").count() > 0
                if has_value:
                    existing_value = await select_container.locator("div.select__single-value").inner_text()
                    logger.info(f"⚠️ Dropdown already has value: '{existing_value}' - skipping")
                    return True
                
                # Find the clickable control area
                control = select_container.locator("div.select__control")
                if await control.count() == 0:
                    logger.warning("No control found in this select container")
                    continue
                
                # Scroll into view and click to open
                await control.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)
                
                # Click the control to open dropdown
                await control.click(timeout=5000)
                logger.info("📂 Opened dropdown")
                await asyncio.sleep(1.0)  # Wait for options to render
                
                # Wait for menu to appear and find options
                # React-Select typically creates options in the DOM when opened
                option_selectors = [
                    "div.select__option",
                    "[id*='react-select'][id*='option']",
                    "div[role='option']",
                    "div.select__menu div[class*='option']",
                ]
                
                options = None
                for opt_selector in option_selectors:
                    try:
                        temp_options = frame.locator(opt_selector)
                        await temp_options.first.wait_for(state="visible", timeout=3000)
                        opt_count = await temp_options.count()
                        if opt_count > 0:
                            options = temp_options
                            logger.info(f"✅ Found {opt_count} options using selector: {opt_selector}")
                            break
                    except Exception as e:
                        logger.debug(f"Selector {opt_selector} failed: {e}")
                        continue
                
                if not options or await options.count() == 0:
                    logger.warning("⚠️ No options found after opening dropdown")
                    # Try keyboard navigation as fallback
                    return await _keyboard_select_fallback(control, answer)
                
                # Get all option texts
                all_option_texts = []
                for i in range(await options.count()):
                    try:
                        opt_text = await options.nth(i).inner_text()
                        all_option_texts.append(opt_text.strip())
                    except:
                        continue
                
                logger.debug(f"Available options: {all_option_texts}")
                
                # Match the answer to an option
                chosen_option = _match_answer_to_option(answer, all_option_texts)
                
                if not chosen_option:
                    logger.warning(f"⚠️ Could not match answer '{answer}' to any option")
                    # Select first option as fallback
                    chosen_option = all_option_texts[0] if all_option_texts else None
                
                if chosen_option:
                    logger.info(f"🎯 Selecting: '{chosen_option}'")
                    
                    # Find and click the matching option
                    for i in range(await options.count()):
                        opt = options.nth(i)
                        opt_text = await opt.inner_text()
                        if opt_text.strip() == chosen_option:
                            await opt.click(timeout=3000)
                            logger.info(f"✅ Successfully selected '{chosen_option}'")
                            await asyncio.sleep(0.5)
                            
                            # Verify selection
                            try:
                                selected = await select_container.locator("div.select__single-value").inner_text()
                                logger.info(f"✅ Verified selection: '{selected}'")
                            except:
                                pass
                            
                            return True
                    
                return False
                
            except Exception as e:
                logger.debug(f"Error processing select container: {e}")
                continue
        
        logger.warning(f"⚠️ Could not find dropdown for '{question_label}'")
        return False
        
    except Exception as e:
        logger.error(f"❌ safe_fill_greenhouse_dropdown error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    

# --- Main Autofill Runner ---
async def run_playwright_autofill(
    job_url: str,
    resume_path: str,
    parsed_resume: dict,
    gist_answers: dict = None,
    manual_submit: bool = True,
    detect_only: bool = False,
):
    mode = "detect_only" if detect_only else ("manual_submit_mode" if manual_submit else "autofill")
    
    # 🔒 Acquire semaphore - max 3 concurrent browsers
    # EVERYTHING below must be indented inside this block!
    async with playwright_semaphore:
        logger.info(f"⏳ Waiting for Playwright slot...")
        logger.info(f"🔒 Playwright slot ACQUIRED (max 3 concurrent)")
        logger.info(f"🌍 Navigating to {job_url} ({mode})")
        
        gist_answers = gist_answers or {}
        logger.info(f"🧩 Loaded gist answers: {len(gist_answers)}")
        
        if gist_answers:
            logger.debug("📋 Gist answers received:")
            for key, val in gist_answers.items():
                logger.debug(f"  - {key}: {str(val)[:100]}")
        else:
            logger.warning("⚠️⚠️⚠️ NO GIST ANSWERS PROVIDED! Dropdowns will fail!")
        
        try:
            async with async_playwright() as pw:
                HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
                browser = await pw.chromium.launch(headless=HEADLESS if detect_only else False, slow_mo=100)
                page = await browser.new_page()

                try:
                    await page.goto(job_url, timeout=60000)
                    await page.wait_for_load_state("networkidle")

                    # --- Click Apply Now ---
                    clicked = False
                    for sel in [
                        "button:has-text('Apply Now')",
                        "a:has-text('Apply Now')",
                        "text=Apply Now",
                        "[data-mapped='apply_button']",
                        ".app-btn-apply",
                        "[data-test='apply-button']",
                    ]:
                        try:
                            if await page.locator(sel).count() > 0:
                                await page.locator(sel).first.click(timeout=7000)
                                clicked = True
                                logger.info(f"✅ Clicked Apply Now via {sel}")
                                break
                        except Exception:
                            continue
                    if not clicked:
                        logger.warning("⚠️ Could not click Apply Now; continuing anyway.")

                    await page.wait_for_timeout(1500)

                    # --- Detect form frame ---
                    target_frame = None
                    current_url = page.url.lower()
                    if any(x in current_url for x in ["greenhouse", "lever", "workday"]):
                        target_frame = page.main_frame
                        logger.info("🌿 Detected known ATS form.")
                    else:
                        for f in page.frames:
                            if any(x in (f.url or "").lower() for x in ["greenhouse", "application", "boards"]):
                                target_frame = f
                                logger.info(f"🪟 Using iframe: {f.url}")
                                break

                    frame_ctx = target_frame if target_frame else page.main_frame
                    await frame_ctx.wait_for_selector("input, textarea, select", timeout=20000)
                    logger.info("✅ Form detected!")

                    # --- Extract fields ---
                    detected_fields = await frame_ctx.evaluate(
                        """() => {
                            const els = Array.from(document.querySelectorAll('input, textarea, select'));
                            const visible = els.filter(el => {
                                const s = window.getComputedStyle(el);
                                return s && s.display !== 'none' && s.visibility !== 'hidden' && el.offsetParent !== null;
                            });
            
                            return visible.map(el => {
                                let labelText = '';
                    
                                // Strategy 1: Check if inside a label
                                const parentLabel = el.closest('label');
                                if (parentLabel) {
                                    labelText = parentLabel.innerText.trim();
                                }
                
                                // Strategy 2: Check aria-labelledby (for React-Select dropdowns)
                                if (!labelText) {
                                    const ariaLabelledBy = el.getAttribute('aria-labelledby');
                                    if (ariaLabelledBy) {
                                        const labelEl = document.getElementById(ariaLabelledBy);
                                        if (labelEl) {
                                            labelText = labelEl.innerText.trim();
                                        }
                                    }
                                }
                
                                // Strategy 3: Check for label with matching 'for' attribute
                                if (!labelText && el.id) {
                                    const labelFor = document.querySelector(`label[for="${el.id}"]`);
                                    if (labelFor) {
                                        labelText = labelFor.innerText.trim();
                                    }
                                }
                
                                // Strategy 4: Check for preceding label sibling
                                if (!labelText) {
                                    let sibling = el.previousElementSibling;
                                    while (sibling) {
                                        if (sibling.tagName === 'LABEL') {
                                            labelText = sibling.innerText.trim();
                                            break;
                                        }
                                        sibling = sibling.previousElementSibling;
                                    }
                                }
                
                                // Strategy 5: Check aria-label attribute
                                if (!labelText) {
                                    labelText = el.getAttribute('aria-label') || '';
                                }
                
                                return {
                                    tag: el.tagName.toLowerCase(),
                                    name: el.name || null,
                                    id: el.id || null,
                                    placeholder: el.placeholder || null,
                                    aria_label: el.getAttribute('aria-label') || null,
                                    label_text: labelText,
                                    type: el.type || null
                                };
                            });
                        }"""
                    )
                    logger.info(f"🧾 Found {len(detected_fields)} fields on form.")

                    if not detect_only:
                        logger.debug("📋 Detected field labels:")
                        for field in detected_fields[:15]:
                            label = field.get('label_text') or field.get('aria_label') or field.get('placeholder') or field.get('name')
                            logger.debug(f"  - {label}")

                    if detect_only:
                        await browser.close()
                        return {"status": "success", "mode": "detect_only", "detected_fields": detected_fields}

                    # --- Helpers ---
                    async def safe_fill_selector(frame, selector: str, value: str) -> bool:
                        if not value or not selector:
                            return False
                        try:
                            locator = frame.locator(selector)
                            if await locator.count() == 0:
                                return False
                            el = locator.first
                            try:
                                await el.scroll_into_view_if_needed(timeout=5000)
                            except Exception as e:
                                logger.debug(f"Scroll into view failed quickly: {e}")
                                return False
                            tag = await el.evaluate("(el) => el.tagName.toLowerCase()")
                            if tag == "select":
                                options = await el.locator("option").all_inner_texts()
                                chosen = None
                                for opt in options:
                                    if value.lower() in opt.lower() or opt.lower() in value.lower():
                                        chosen = opt
                                        break
                                if not chosen:
                                    if value.strip().lower().startswith("y"):
                                        chosen = next((o for o in options if "yes" in o.lower()), None)
                                    elif value.strip().lower().startswith("n"):
                                        chosen = next((o for o in options if "no" in o.lower()), None)
                                if chosen:
                                    await el.select_option(label=chosen)
                                    logger.info(f"✅ Selected option '{chosen}' for {selector}")
                                    return True
                                return False

                            await el.click(timeout=1500)
                            await asyncio.sleep(random.uniform(0.15, 0.45))
                            await el.fill(str(value)[:800])
                            return True
                        except Exception as e:
                            logger.debug(f"safe_fill fail: {e}")
                            return False

                    async def safe_click_choice(frame, group_name: str, desired_answer: str) -> bool:
                        if not group_name or not desired_answer:
                            return False
                        try:
                            radios = frame.locator(f"input[name='{group_name}'], input[id*='{group_name}']")
                            count = await radios.count()
                            for i in range(count):
                                r = radios.nth(i)
                                lbl = await r.evaluate(
                                    "(el) => { const l = el.closest('label'); if(l) return l.innerText||''; const id = el.id; if(id){ const lab = document.querySelector(`label[for='${id}']`); return lab ? lab.innerText : ''; } return ''; }"
                                )
                                if lbl and desired_answer.lower() in lbl.lower():
                                    await r.scroll_into_view_if_needed()
                                    await r.click()
                                    return True
                            for i in range(count):
                                r = radios.nth(i)
                                val = await r.get_attribute("value") or ""
                                if desired_answer.lower() in val.lower():
                                    await r.scroll_into_view_if_needed()
                                    await r.click()
                                    return True
                                if desired_answer.strip().lower().startswith("y") and "yes" in val.lower():
                                    await r.scroll_into_view_if_needed()
                                    await r.click()
                                    return True
                                if desired_answer.strip().lower().startswith("n") and "no" in val.lower():
                                    await r.scroll_into_view_if_needed()
                                    await r.click()
                                    return True
                            return False
                        except Exception as e:
                            logger.debug(f"safe_click_choice fail: {e}")
                            return False

                    # --- Fill core fields ---
                    logger.info("📝 Filling core fields...")
                    for fld in ["first_name", "last_name", "email", "phone"]:
                        val = parsed_resume.get(fld)
                        if not val:
                            continue
                        css_candidates = [
                            f"input[name*='{fld}']",
                            f"input[id*='{fld}']",
                            f"input[aria-label*='{fld}']",
                            f"textarea[name*='{fld}']",
                        ]
                        for sel in css_candidates:
                            if await safe_fill_selector(frame_ctx, sel, val):
                                logger.info(f"✅ Filled {fld} using {sel}")
                                break

                    # --- Upload resume ---
                    logger.info("📎 Uploading resume...")
                    for fs in [
                        "input[type='file'][id*='resume']",
                        "input[type='file'][name*='resume']",
                        "input[type='file'][id*='attach']",
                        "input[type='file']",
                    ]:
                        try:
                            loc = frame_ctx.locator(fs)
                            if await loc.count() > 0:
                                await loc.first.set_input_files(resume_path)
                                logger.info(f"✅ Uploaded resume via {fs}")
                                break
                        except Exception:
                            continue

                    # --- Fill dynamic fields ---
                    logger.info("📋 Filling dynamic fields...")
                    for field in detected_fields:
                        label = (field.get("aria_label") or field.get("label_text") or field.get("placeholder") or "").strip()
                        name = field.get("name") or field.get("id") or ""
                        tag = field.get("tag") or "input"
                        ftype = (field.get("type") or "").lower()

                        if not label and not name:
                            continue
                        if ftype == "file":
                            continue
        
                        if "select__input" in (field.get("id") or ""):
                            logger.debug(f"⏭️ Skipping dropdown input: {label or name}")
                            continue
        
                        if label and any(q in label for q in [
                            "What is your total years of experience",
                            "Do you have at least",
                            "Do you have any experience",
                            "Do you use AI Tools",
                            "Would you be open to relocating",
                            "When is your notice period"
                        ]):
                            logger.debug(f"⏭️ Skipping (will be handled by dropdown logic): {label}")
                            continue

                        answer = find_best_answer(label or name, gist_answers, parsed_resume)
                        
                        if not answer and any(w in (label or name).lower() for w in ["location", "city", "state", "country"]):
                            answer = parsed_resume.get("location") or "Bengaluru, Karnataka, India"

                        if not answer:
                            continue

                        label_snip_css = _css_escape((label or name)[:30].lower())
                        label_snip_xpath = (label or name)[:80]

                        if "select__input" in (field.get("id") or ""):
                            continue

                        filled = False

                        if ftype in ("radio", "checkbox"):
                            group_name = name or label_snip_css
                            if group_name and await safe_click_choice(frame_ctx, group_name, answer):
                                logger.info(f"✅ Clicked choice for '{label or name}' → {answer}")
                                continue

                        selectors_to_try = []
                        if label_snip_css:
                            selectors_to_try += [
                                f"[aria-label*=\"{label_snip_css}\"]",
                                f"[placeholder*=\"{label_snip_css}\"]",
                                f"[name*=\"{label_snip_css}\"]",
                                f"[id*=\"{label_snip_css}\"]",
                            ]
                        prefixed = []
                        for s in selectors_to_try:
                            prefixed.append(f"input{s}")
                            prefixed.append(f"textarea{s}")
                            prefixed.append(f"select{s}")
                        selectors_to_try = prefixed + selectors_to_try

                        if label_snip_xpath:
                            esc = _escape_for_xpath(label_snip_xpath.lower())
                            selectors_to_try = [
                                f"xpath=//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {esc})]/following::input[1]",
                                f"xpath=//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {esc})]/following::textarea[1]",
                                f"xpath=//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {esc})]/following::select[1]",
                            ] + selectors_to_try

                        for sel in selectors_to_try:
                            if await safe_fill_selector(frame_ctx, sel, answer):
                                filled = True
                                logger.info(f"✅ Filled '{label or name}' using {sel} → {str(answer)[:120]}")
                                break

                        if not filled and name:
                            sel_by_name = f"select[name='{name}']"
                            if await frame_ctx.locator(sel_by_name).count() > 0:
                                if await safe_fill_selector(frame_ctx, sel_by_name, answer):
                                    logger.info(f"✅ Selected dropdown '{label or name}' using name selector.")
                                    continue

                    # --- Handle Greenhouse React dropdowns ---
                    logger.info("🎯 Handling Greenhouse dropdowns...")
                    
                    all_select_containers = await frame_ctx.locator("div.select__container").all()
                    logger.info(f"Found {len(all_select_containers)} Greenhouse dropdown(s)")
                    
                    for select_container in all_select_containers:
                        try:
                            label_elem = select_container.locator("label.select__label")
                            if await label_elem.count() == 0:
                                continue
                            
                            label_text = await label_elem.inner_text()
                            label_clean = label_text.replace('*', '').strip()
                            
                            has_value = await select_container.locator("div.select__single-value").count() > 0
                            if has_value:
                                logger.debug(f"Dropdown '{label_clean}' already filled")
                                continue
                            
                            answer = find_best_answer(label_clean, gist_answers, parsed_resume)
                            
                            if not answer:
                                logger.warning(f"⚠️ No answer found for dropdown: '{label_clean}'")
                                continue
                            
                            logger.info(f"🔄 Attempting to fill dropdown: '{label_clean}'")
                            success = await safe_fill_greenhouse_dropdown(frame_ctx, label_clean, answer)
                            
                            if not success:
                                logger.warning(f"⚠️ Failed to fill dropdown: '{label_clean}'")
                        
                        except Exception as e:
                            logger.debug(f"Error processing dropdown: {e}")
                            continue

                    # --- Screenshot ---
                    screenshot_path = os.path.join(os.getcwd(), f"form_filled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"📸 Saved screenshot: {screenshot_path}")

                    if manual_submit:
                        logger.info("👀 Please review and click Submit manually.")
                        logger.info("⏳ Waiting for you to close the browser...")
                        try:
                            await page.wait_for_event("close", timeout=0)
                        except Exception as e:
                            logger.warning(f"⚠️ Browser close event error: {e}")
                            logger.info("⏳ Auto-closing in 5 minutes...")
                            await asyncio.sleep(300)

                    await browser.close()
                    return {
                        "status": "success",
                        "message": "Form autofilled successfully (Greenhouse dropdowns included)",
                        "screenshot": screenshot_path,
                    }

                except Exception as e:
                    logger.error(f"❌ Error during autofill: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error(f"❌ Playwright session failed: {e}")
            return {"status": "error", "message": str(e)}  




