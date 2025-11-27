import { useState, useEffect, useRef } from 'react';
import { applyToJob } from '../services/api';

export default function Step3_AutoFill({ resetFlow, setCurrentStep, resumeFile, jobUrl }) {
  const [status, setStatus] = useState('preparing');
  const [error, setError] = useState(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const fillForm = async () => {
      try {
        await applyToJob(resumeFile, jobUrl);
        setStatus('ready');
      } catch (err) {
        setStatus('error');
        setError('Failed to open form. Please try again.');
      }
    };

    fillForm();
  }, [resumeFile, jobUrl]);

  const handleRetryAutoFill = async () => {
    setError(null);
    setStatus('preparing');
    setHasSubmitted(false);
    try {
      await applyToJob(resumeFile, jobUrl);
      setStatus('ready');
    } catch (err) {
      setStatus('error');
      setError('Failed to re-open form.');
    }
  };

  // PREPARING STATE
  if (status === 'preparing') {
    return (
      <div className="bg-white dark:bg-bumblebee-gray-900 rounded-2xl shadow-xl dark:shadow-bumblebee-yellow/10 p-8 transition-colors border dark:border-bumblebee-gray-800">
        <div className="text-center mb-6">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 dark:border-bumblebee-yellow mb-4 mx-auto"></div>
          <h2 className="text-2xl font-bold text-gray-800 dark:text-bumblebee-yellow mb-2">
            Opening Your Application...
          </h2>
          <p className="text-gray-600 dark:text-bumblebee-gray-300">
            This takes 5-10 seconds. Get ready!
          </p>
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-bumblebee-gray-800 dark:to-bumblebee-gray-800 border-l-4 border-blue-600 dark:border-bumblebee-yellow p-6 mb-6 rounded-r-lg">
          <h3 className="font-bold text-gray-800 dark:text-white mb-3">📝 What will happen:</h3>
          <ol className="text-sm text-gray-700 dark:text-bumblebee-gray-300 space-y-3">
            <li className="flex items-start">
              <span className="font-bold mr-2 text-blue-600 dark:text-bumblebee-yellow">1.</span>
              <span><strong>A new tab will open automatically</strong> with the job application</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2 text-blue-600 dark:text-bumblebee-yellow">2.</span>
              <span><strong>All fields will be pre-filled</strong> with your resume information</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2 text-blue-600 dark:text-bumblebee-yellow">3.</span>
              <span><strong>Review everything carefully</strong> - check all details are correct</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2 text-blue-600 dark:text-bumblebee-yellow">4.</span>
              <span><strong>Make any edits</strong> if needed</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2 text-blue-600 dark:text-bumblebee-yellow">5.</span>
              <span><strong>Click "Submit Application"</strong> button on that page</span>
            </li>
            <li className="flex items-start">
              <span className="font-bold mr-2 text-green-600 dark:text-bumblebee-gold">✓</span>
              <span><strong>Wait for email confirmation</strong> from the company</span>
            </li>
          </ol>
        </div>

        <div className="bg-yellow-50 dark:bg-bumblebee-yellow/10 border-l-4 border-yellow-500 dark:border-bumblebee-amber p-4 rounded-r-lg">
          <p className="text-sm text-gray-700 dark:text-bumblebee-gray-300">
            <strong>💡 Tip:</strong> Keep this tab open. If you accidentally close the form, you can re-open it from here.
          </p>
        </div>
      </div>
    );
  }

  // READY STATE
  if (status === 'ready') {
    return (
      <div className="bg-white dark:bg-bumblebee-gray-900 rounded-2xl shadow-xl dark:shadow-bumblebee-yellow/10 p-8 transition-colors border dark:border-bumblebee-gray-800">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 dark:bg-bumblebee-yellow/20 rounded-full mb-4 border-2 dark:border-bumblebee-yellow">
            <svg className="w-12 h-12 text-green-600 dark:text-bumblebee-yellow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-gray-800 dark:text-bumblebee-yellow mb-2">
            Tab Opened Successfully! 🎉
          </h2>
          <p className="text-lg text-gray-600 dark:text-bumblebee-gray-300">
            Switch to the new tab to review and submit your application
          </p>
        </div>

        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-bumblebee-gray-800 dark:to-bumblebee-gray-800 border-l-4 border-blue-600 dark:border-bumblebee-yellow p-6 mb-6 rounded-r-lg">
          <p className="text-sm text-gray-700 dark:text-bumblebee-gray-300">
            <strong className="text-gray-800 dark:text-white">✓ Your application form is ready</strong>
            <br /><br />
            Switch to the Greenhouse tab, review the pre-filled information, and click Submit when ready.
            <br /><br />
            <strong className="text-gray-800 dark:text-white">After submitting:</strong> Come back here and check the box below.
          </p>
        </div>

        {/* Submission Confirmation Checkbox */}
        <div className="bg-gray-50 dark:bg-bumblebee-gray-800 border border-gray-200 dark:border-bumblebee-gray-700 rounded-lg p-4 mb-6">
          <label className="flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={hasSubmitted}
              onChange={(e) => setHasSubmitted(e.target.checked)}
              className="w-5 h-5 mr-3 cursor-pointer accent-indigo-600 dark:accent-bumblebee-yellow"
            />
            <span className="text-sm font-medium text-gray-700 dark:text-bumblebee-gray-300">
              ✅ I have reviewed and submitted the application
            </span>
          </label>
        </div>

        {hasSubmitted && (
          <div className="bg-green-50 dark:bg-bumblebee-yellow/10 border-l-4 border-green-600 dark:border-bumblebee-yellow p-4 mb-6 rounded-r-lg">
            <p className="text-sm text-green-700 dark:text-bumblebee-yellow">
              <strong>🎉 Great job!</strong> Check your email for confirmation from the company.
            </p>
          </div>
        )}

        <div className="space-y-3">
          {!hasSubmitted && (
            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep(2)}
                className="flex-1 bg-gray-100 dark:bg-bumblebee-gray-800 hover:bg-gray-200 dark:hover:bg-bumblebee-gray-700 text-gray-700 dark:text-bumblebee-gray-300 font-semibold py-3 px-4 rounded-lg transition-colors border border-gray-300 dark:border-bumblebee-gray-700"
              >
                ← View Match Score
              </button>
              <button
                onClick={handleRetryAutoFill}
                className="flex-1 bg-blue-600 dark:bg-bumblebee-gold hover:bg-blue-700 dark:hover:bg-bumblebee-yellow text-white dark:text-bumblebee-dark font-semibold py-3 px-4 rounded-lg transition-colors shadow-lg dark:shadow-bumblebee-yellow/20"
              >
                🔄 Re-open Form
              </button>
            </div>
          )}
          
          <button
            onClick={resetFlow}
            className="w-full bg-indigo-600 hover:bg-indigo-700 dark:bg-bumblebee-yellow dark:hover:bg-bumblebee-gold text-white dark:text-bumblebee-dark font-bold py-3 px-4 rounded-lg transition-colors shadow-lg dark:shadow-bumblebee-yellow/20"
          >
            Apply to {hasSubmitted ? 'Another' : 'Different'} Job
          </button>
        </div>

        {!hasSubmitted && (
          <p className="text-center text-sm text-gray-500 dark:text-bumblebee-gray-500 mt-6">
            Don't see the new tab? Check if your browser blocked popups.
          </p>
        )}
      </div>
    );
  }

  // ERROR STATE
  if (status === 'error') {
    return (
      <div className="bg-white dark:bg-bumblebee-gray-900 rounded-2xl shadow-xl dark:shadow-bumblebee-yellow/10 p-8 transition-colors border dark:border-bumblebee-gray-800">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-red-100 dark:bg-red-900/30 rounded-full mb-4 border-2 dark:border-red-700">
            <svg className="w-12 h-12 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">
            Something Went Wrong
          </h2>
          <p className="text-gray-600 dark:text-bumblebee-gray-400 mb-6">{error}</p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => setCurrentStep(2)}
            className="flex-1 bg-gray-600 hover:bg-gray-700 dark:bg-bumblebee-gray-700 dark:hover:bg-bumblebee-gray-600 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
          >
            ← View Match Score
          </button>
          <button
            onClick={handleRetryAutoFill}
            className="flex-1 bg-blue-600 hover:bg-blue-700 dark:bg-bumblebee-yellow dark:hover:bg-bumblebee-gold text-white dark:text-bumblebee-dark font-semibold py-3 px-4 rounded-lg transition-colors shadow-lg dark:shadow-bumblebee-yellow/20"
          >
            🔄 Try Again
          </button>
        </div>
      </div>
    );
  }
}