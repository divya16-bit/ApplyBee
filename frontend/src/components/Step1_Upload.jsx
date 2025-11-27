import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { getATSScore } from '../services/api';

export default function Step1_Upload({
  resumeFile,
  setResumeFile,
  jobUrl,
  setJobUrl,
  setCurrentStep,
  setLoading,
  setError,
  setAtsData,
}) {
  const [urlError, setUrlError] = useState('');

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setResumeFile(acceptedFiles[0]);
      }
    },
  });

  const validateGreenhouseUrl = (url) => {
    const pattern = /^https?:\/\/(boards\.|job-boards\.)?greenhouse\.io\/.+\/jobs\/\d+/i;
    return pattern.test(url);
  };

  const handleAnalyze = async () => {
    setError(null);
    setUrlError('');

    if (!resumeFile) {
      setError('Please upload your resume');
      return;
    }

    if (!jobUrl.trim()) {
      setUrlError('Please enter a job URL');
      return;
    }

    if (!validateGreenhouseUrl(jobUrl)) {
      setUrlError('Please enter a valid Greenhouse job URL');
      return;
    }

    try {
      setLoading(true);
      const data = await getATSScore(resumeFile, jobUrl);
      setAtsData(data);
      setCurrentStep(2);
    } catch (err) {
      const errorMessage = err.message || err.response?.data?.detail || 'Failed to analyze resume. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-bumblebee-gray-900 rounded-2xl shadow-xl dark:shadow-bumblebee-yellow/10 p-8 transition-colors border dark:border-bumblebee-gray-800">
      <h2 className="text-3xl font-bold text-gray-800 dark:text-bumblebee-yellow mb-6">
        Let's Get Started 🚀
      </h2>

      {/* Resume Upload */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-700 dark:text-bumblebee-gray-300 mb-2">
          Upload Your Resume
        </label>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
            isDragActive
              ? 'border-indigo-600 dark:border-bumblebee-yellow bg-indigo-50 dark:bg-bumblebee-yellow/10'
              : 'border-gray-300 dark:border-bumblebee-gray-700 hover:border-indigo-400 dark:hover:border-bumblebee-yellow'
          }`}
        >
          <input {...getInputProps()} />
          {resumeFile ? (
            <div className="text-green-600 dark:text-bumblebee-yellow">
              <svg
                className="w-12 h-12 mx-auto mb-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9 2a2 2 0 00-2 2v8a2 2 0 002 2h6a2 2 0 002-2V6.414A2 2 0 0016.414 5L14 2.586A2 2 0 0012.586 2H9z" />
              </svg>
              <p className="font-semibold text-gray-800 dark:text-white">{resumeFile.name}</p>
              <p className="text-sm text-gray-500 dark:text-bumblebee-gray-400">
                {(resumeFile.size / 1024).toFixed(2)} KB
              </p>
            </div>
          ) : (
            <div className="text-gray-500 dark:text-bumblebee-gray-400">
              <svg
                className="w-12 h-12 mx-auto mb-2"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p className="text-lg">
                Drag & drop your resume here, or click to browse
              </p>
              <p className="text-sm mt-1">PDF or DOCX (max 10MB)</p>
            </div>
          )}
        </div>
      </div>

      {/* Job URL Input */}
      <div className="mb-8">
        {/* Label with Badge */}
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-semibold text-gray-700 dark:text-bumblebee-gray-300">
            Greenhouse Job URL
          </label>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 border border-green-200 dark:border-green-800">
            Greenhouse Only
          </span>
        </div>

        {/* Input Field */}
        <input
          type="url"
          value={jobUrl}
          onChange={(e) => {
            setJobUrl(e.target.value);
            setUrlError('');
          }}
          placeholder="Paste Greenhouse job link here"
          className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 bg-white dark:bg-bumblebee-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-bumblebee-gray-500 transition-colors ${
            urlError
              ? 'border-red-500 focus:ring-red-500'
              : jobUrl && validateGreenhouseUrl(jobUrl)
              ? 'border-green-500 dark:border-green-600 focus:ring-green-500'
              : 'border-gray-300 dark:border-bumblebee-gray-700 focus:ring-indigo-500 dark:focus:ring-bumblebee-yellow'
          }`}
        />

        {/* Format Example - Always Visible */}
        <p className="text-xs text-gray-500 dark:text-bumblebee-gray-400 mt-2 flex items-start">
          <span className="mr-1.5 mt-0.5">📋</span>
          <span>
            Expected format: <code className="bg-gray-100 dark:bg-bumblebee-gray-800 px-1.5 py-0.5 rounded text-gray-700 dark:text-bumblebee-gray-300">https://boards.greenhouse.io/[company]/jobs/[job-id]</code>
          </span>
        </p>

        {/* Validation Success */}
        {jobUrl && validateGreenhouseUrl(jobUrl) && !urlError && (
          <p className="text-green-600 dark:text-green-400 text-sm mt-2 flex items-center font-medium">
            <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Valid Greenhouse URL
          </p>
        )}

        {/* Error Message */}
        {urlError && (
          <p className="text-red-500 dark:text-red-400 text-sm mt-2 flex items-center font-medium">
            <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            {urlError}
          </p>
        )}
      </div>

      {/* Submit Button */}
      <button
        onClick={handleAnalyze}
        className="w-full bg-indigo-600 hover:bg-indigo-700 dark:bg-bumblebee-yellow dark:hover:bg-bumblebee-gold text-white dark:text-bumblebee-dark font-bold py-4 px-6 rounded-lg transition-colors text-lg shadow-lg dark:shadow-bumblebee-yellow/20"
      >
        Analyze Match 🐝
      </button>
    </div>
  );
}