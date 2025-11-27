import { useState } from 'react';
import Step1_Upload from './components/Step1_Upload';
import Step2_ATSScore from './components/Step2_ATSScore';
import Step3_AutoFill from './components/Step3_AutoFill';
import Loader from './components/Loader';
import DarkModeToggle from './components/DarkModeToggle';
import Footer from './components/Footer';
import useDarkMode from './hooks/useDarkMode';

function App() {
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [resumeFile, setResumeFile] = useState(null);
  const [jobUrl, setJobUrl] = useState('');
  const [atsData, setAtsData] = useState(null);

  const [isDark, setIsDark] = useDarkMode();

  const resetFlow = () => {
    setCurrentStep(1);
    setResumeFile(null);
    setJobUrl('');
    setAtsData(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-bumblebee-darker dark:to-bumblebee-dark transition-colors">
      {/* Dark Mode Toggle */}
      <DarkModeToggle isDark={isDark} setIsDark={setIsDark} />

      <div className="container mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-800 dark:text-bumblebee-yellow mb-4">
            ApplyBee 🐝
          </h1>
          <p className="text-xl text-gray-600 dark:text-bumblebee-gray-300">
            Smart Resume Matching + Auto-Fill Application
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="max-w-3xl mx-auto mb-8">
          <div className="flex items-center justify-between">
            {[1, 2, 3].map((step) => (
              <div key={step} className="flex items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-colors ${
                    currentStep >= step
                      ? 'bg-indigo-600 dark:bg-bumblebee-yellow text-white dark:text-bumblebee-dark'
                      : 'bg-gray-300 dark:bg-bumblebee-gray-700 text-gray-600 dark:text-bumblebee-gray-400'
                  }`}
                >
                  {step}
                </div>
                {step < 3 && (
                  <div
                    className={`w-24 h-1 mx-2 transition-colors ${
                      currentStep > step 
                        ? 'bg-indigo-600 dark:bg-bumblebee-yellow' 
                        : 'bg-gray-300 dark:bg-bumblebee-gray-700'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-2 text-sm text-gray-600 dark:text-bumblebee-gray-400">
            <span>Upload</span>
            <span>Match Score</span>
            <span>Auto-fill</span>
          </div>
        </div>

        {/* Main Content */}
        <div className="max-w-4xl mx-auto">
          {loading && <Loader />}
          
          {error && (
            <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-700 text-red-700 dark:text-red-300 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {!loading && (
            <>
              {currentStep === 1 && (
                <Step1_Upload
                  resumeFile={resumeFile}
                  setResumeFile={setResumeFile}
                  jobUrl={jobUrl}
                  setJobUrl={setJobUrl}
                  setCurrentStep={setCurrentStep}
                  setLoading={setLoading}
                  setError={setError}
                  setAtsData={setAtsData}
                />
              )}

              {currentStep === 2 && (
                <Step2_ATSScore
                  atsData={atsData}
                  resetFlow={resetFlow}
                  setCurrentStep={setCurrentStep}
                  resumeFile={resumeFile}
                  jobUrl={jobUrl}
                />
              )}

              {currentStep === 3 && (
                <Step3_AutoFill 
                  resetFlow={resetFlow}
                  setCurrentStep={setCurrentStep}
                  resumeFile={resumeFile}
                  jobUrl={jobUrl}
                />
              )}
            </>
          )}
        </div>
        <Footer />
      </div>
    </div>
  );
}

export default App;