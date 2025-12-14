# app/services/skill_normalizer.py
from sentence_transformers import SentenceTransformer, util
import os


# Lazy load model
_model = None

def get_normalizer_model():
    global _model
    if _model is None:
        print("🔄 Loading normalizer model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Normalizer model loaded")
    return _model

# Pre-load if semantic matching enabled for normalizer
# Check both legacy MATCHER_SEMANTIC and new MATCHER_SEMANTIC_NORMALIZER
USE_NORMALIZER = (
    os.getenv("MATCHER_SEMANTIC_NORMALIZER", "1") != "0" or
    (os.getenv("MATCHER_SEMANTIC", "") != "0" and os.getenv("MATCHER_SEMANTIC", "") != "")
)
if USE_NORMALIZER:
    try:
        model = get_normalizer_model()
    except Exception as e:
        print(f"⚠️ Could not pre-load normalizer: {e}")
        model = None
else:
    model = None

# Cache category embeddings for performance (encode once, reuse many times)
_category_embeddings_cache = {}

def _get_category_embeddings(category, examples):
    """Get cached embeddings for a category's examples."""
    if category not in _category_embeddings_cache:
        if model is not None:
            try:
                _category_embeddings_cache[category] = model.encode(examples, convert_to_tensor=True)
            except Exception:
                _category_embeddings_cache[category] = None
        else:
            _category_embeddings_cache[category] = None
    return _category_embeddings_cache[category]

# Expanded canonical categories
CATEGORIES = {
    # Core programming
    "programming_languages": [
        "python", "java", "c++", "c#", "javascript", "typescript", "go", "rust", "ruby",
        "php", "swift", "kotlin", "scala", "r", "perl", "objective-c"
    ],
    # Frontend frameworks & UI
    "frontend_frameworks": [
        "react", "reactjs", "react.js", "angular", "vue", "svelte", "ember",
        "nextjs", "nuxtjs", "backbone", "jquery"
    ],
    "frontend_tools": [
        "html", "css", "sass", "less", "tailwind", "bootstrap", "material-ui",
        "webpack", "babel", "vite", "eslint", "storybook"
    ],
    # Backend frameworks
    "backend_frameworks": [
        "django", "flask", "spring", "spring boot", "express", "fastapi",
        "rails", "laravel", "dotnet", "asp.net", "phoenix"
    ],
    # Databases
    "databases": [
        "mysql", "postgresql", "postgres", "oracle", "mongodb", "cassandra",
        "dynamodb", "redis", "couchdb", "elasticsearch", "neo4j", "sqlite", "sql server"
    ],
    "api_development": [
    "api", "rest", "restful", "graphql", "soap", 
    "openapi", "swagger", "postman", "api design",
    "api testing", "api integration" , "apis"
    ],

    # DevOps / Infra
    "cloud_platforms": [
        "aws", "azure", "gcp", "google cloud", "cloud foundry", "heroku", "openstack"
    ],
    "containers": [
        "docker", "kubernetes", "container orchestration", "helm", "openshift"
    ],
    "infra_as_code": [
        "terraform", "ansible", "chef", "puppet", "saltstack", "pulumi"
    ],
    "ci_cd": [
        "ci/cd", "jenkins", "github actions", "gitlab ci", "azure pipelines",
        "circleci", "travis", "teamcity", "bamboo"
    ],
    # Testing
    "testing": [
        "jest", "mocha", "chai", "junit", "pytest", "nose", "cypress",
        "selenium", "playwright", "karma", "rtl", "unittest", "robot framework"
    ],
    # Data & ML/AI
    "data_processing": [
        "spark", "hadoop", "hive", "pig", "beam", "storm", "flink"
    ],
    "ml_ai": [
        "tensorflow", "pytorch", "scikit-learn", "sklearn", "xgboost", "lightgbm",
        "keras", "theano", "mxnet", "nltk", "spacy", "transformers"
    ],
    "data_analysis": [
        "numpy", "pandas", "matplotlib", "seaborn", "plotly", "powerbi", "tableau", "excel"
    ],
    # Security
    "security": [
        "oauth", "jwt", "saml", "cyberark", "vault", "okta", "ldap", "kerberos",
        "siem", "iam", "ssl", "tls", "mfa", "zero trust"
    ],
    #GenAI/LLM
    "genai_llm": [
    "gpt", "chatgpt", "claude", "gemini", "llama", "llamaindex", "langchain",
    "mistral", "cohere", "anthropic", "openai", "vertex ai", "huggingface",
    "stable diffusion", "midjourney", "copilot", "cursor", "tabnine", "autogen",
    "rag", "agentic ai", "generative ai", "prompt engineering", "vector db",
    "pinecone", "weaviate", "milvus", "faiss"
    ],
    # General tools
    "version_control": [
        "git", "svn", "mercurial"
    ],
    "project_tools": [
        "jira", "confluence", "trello", "asana", "slack", "notion"
    ],
    "observability": [
    "prometheus", "grafana", "datadog", "new relic", "splunk",
    "elk", "elasticsearch", "logstash", "kibana", "opentelemetry",
    "cloudwatch", "dynatrace", "appdynamics", "sentry"
    ]

}



def normalize_skills(raw_skills, threshold: float = 0.6):
    """
    Takes a list of raw skills (strings) and maps them into normalized categories.
    Returns [(original, category, score)].
    Optimized with caching and batch processing.
    """
    if not raw_skills:
        return []
    
    # Get model (should already be loaded)
    m = model if model is not None else get_normalizer_model()
    
    if m is None:
        # Fallback if model couldn't load
        return [(skill, "other", 0.0) for skill in raw_skills]

    # Fast path: For very small lists, use simple string matching (much faster)
    if len(raw_skills) <= 5:
        # For small lists, just check if skills match known category examples
        results = []
        for skill in raw_skills:
            skill_lower = skill.lower()
            # Quick check: is it a known tech skill in any category?
            found_category = "other"
            best_match_score = 0.0
            for cat, examples in CATEGORIES.items():
                # Check exact match first
                if skill_lower in [ex.lower() for ex in examples]:
                    found_category = cat
                    best_match_score = 0.9
                    break
                # Check partial match
                for ex in examples:
                    if skill_lower in ex.lower() or ex.lower() in skill_lower:
                        if len(ex) > 2:  # Avoid matching single letters
                            found_category = cat
                            best_match_score = 0.7
                            break
                if found_category != "other":
                    break
            results.append((skill, found_category, best_match_score))
        return results

    # Batch encode all skills at once (much faster than one-by-one)
    try:
        skill_embeds = model.encode(raw_skills, convert_to_tensor=True, show_progress_bar=False)
    except Exception:
        # Fallback to individual encoding if batch fails
        skill_embeds = None

    results = []
    for idx, skill in enumerate(raw_skills):
        try:
            # Use batch embedding if available, otherwise encode individually
            if skill_embeds is not None:
                skill_embed = skill_embeds[idx:idx+1]  # Get single embedding from batch
            else:
                skill_embed = model.encode(skill, convert_to_tensor=True)
        except Exception:
            results.append((skill, "other", 0.0))
            continue

        best_match = "other"
        best_score = 0.0
        for category, examples in CATEGORIES.items():
            # Use cached embeddings (much faster!)
            example_embeds = _get_category_embeddings(category, examples)
            if example_embeds is None:
                continue
            score = util.cos_sim(skill_embed, example_embeds).max().item()
            if score > best_score:
                best_score = score
                best_match = category

        if best_score >= threshold:
            results.append((skill, best_match, round(best_score, 2)))
        else:
            results.append((skill, "other", round(best_score, 2)))

    return results
