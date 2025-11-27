export default function Step2_ATSScore({
  atsData,
  resetFlow,
  setCurrentStep,
  resumeFile,
  jobUrl,
}) {
  const handleAutoFill = () => {
    setCurrentStep(3);
  };

  const getScoreColor = (score) => {
    if (score >= 70) return 'text-green-600 dark:text-bumblebee-yellow';
    if (score >= 50) return 'text-yellow-600 dark:text-bumblebee-amber';
    return 'text-red-600 dark:text-red-400';
  };

  const getScoreMessage = (score) => {
    if (score >= 70) return '🎉 Strong Match!';
    if (score >= 50) return '⚠️ Moderate Match';
    return '❌ Weak Match';
  };

  return (
    <div className="bg-white dark:bg-bumblebee-gray-900 rounded-2xl shadow-xl dark:shadow-bumblebee-yellow/10 p-8 transition-colors border dark:border-bumblebee-gray-800">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-gray-800 dark:text-bumblebee-yellow mb-2">
          Resume Match Report
        </h2>
        <p className="text-gray-600 dark:text-bumblebee-gray-300">AI-powered analysis of your resume vs job requirements</p>
      </div>

      {/* Main Score */}
      <div className="text-center mb-8 p-8 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-bumblebee-gray-800 dark:to-bumblebee-gray-800 rounded-xl border dark:border-bumblebee-yellow/30">
        <p className="text-lg text-gray-600 dark:text-bumblebee-gray-300 mb-2">Your Match Score</p>
        <div className={`text-7xl font-bold mb-2 ${getScoreColor(atsData.ats_score)}`}>
          {atsData.ats_score.toFixed(1)}%
        </div>
        <p className="text-2xl font-semibold text-gray-700 dark:text-white">{getScoreMessage(atsData.ats_score)}</p>
      </div>

      {/* Score Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-blue-50 dark:bg-bumblebee-gray-800 p-4 rounded-lg border dark:border-bumblebee-yellow/20">
          <p className="text-sm text-gray-600 dark:text-bumblebee-gray-400 mb-1">Skills Match</p>
          <p className="text-2xl font-bold text-blue-600 dark:text-bumblebee-yellow">
            {atsData.skills_score.toFixed(1)}%
          </p>
        </div>
        <div className="bg-purple-50 dark:bg-bumblebee-gray-800 p-4 rounded-lg border dark:border-bumblebee-yellow/20">
          <p className="text-sm text-gray-600 dark:text-bumblebee-gray-400 mb-1">Responsibilities</p>
          <p className="text-2xl font-bold text-purple-600 dark:text-bumblebee-amber">
            {atsData.responsibility_score.toFixed(1)}%
          </p>
        </div>
        <div className="bg-green-50 dark:bg-bumblebee-gray-800 p-4 rounded-lg border dark:border-bumblebee-yellow/20">
          <p className="text-sm text-gray-600 dark:text-bumblebee-gray-400 mb-1">Experience</p>
          <p className="text-2xl font-bold text-green-600 dark:text-bumblebee-gold">
            {atsData.yoe_score.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Matched Skills */}
      <div className="mb-6">
        <h3 className="text-lg font-bold text-gray-800 dark:text-white mb-3 flex items-center">
          <span className="text-green-600 dark:text-bumblebee-yellow mr-2">✅</span>
          Matched Skills ({atsData.common_skills.length})
        </h3>
        <div className="flex flex-wrap gap-2">
          {atsData.common_skills.map((skill, index) => (
            <span
              key={index}
              className="px-3 py-1 bg-green-100 dark:bg-bumblebee-yellow/20 text-green-700 dark:text-bumblebee-yellow rounded-full text-sm font-medium border dark:border-bumblebee-yellow/30"
            >
              {skill}
            </span>
          ))}
        </div>
      </div>

      {/* Missing Skills */}
{atsData.missing_skills && atsData.missing_skills.length > 0 ? (
  <div className="mb-8">
    <h3 className="text-lg font-bold text-gray-800 dark:text-white mb-3 flex items-center">
      <span className="text-red-600 dark:text-red-400 mr-2">⚠️</span>
      Missing Keywords ({atsData.missing_skills.length})
    </h3>
    <div className="flex flex-wrap gap-2">
      {atsData.missing_skills.map((skill, index) => (
        <span
          key={index}
          className="px-3 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-full text-sm font-medium border dark:border-red-700/50"
        >
          {skill}
        </span>
      ))}
    </div>
    <p className="text-sm text-gray-600 dark:text-bumblebee-gray-400 mt-3">
      💡 Tip: Update your resume to include these keywords if you have relevant experience
    </p>
  </div>
) : (
  <div className="mb-8 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
    <p className="text-sm text-blue-700 dark:text-blue-300 flex items-center">
      <span className="mr-2">ℹ️</span>
      {atsData.jd_skills_used && atsData.jd_skills_used.length > 0 
        ? "Great! Your resume covers all the key requirements found in this job posting."
        : "No specific skill requirements were extracted from this job posting. The job description may not have a structured requirements section."}
    </p>
  </div>
)}

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={resetFlow}
          className="flex-1 bg-gray-200 dark:bg-bumblebee-gray-800 hover:bg-gray-300 dark:hover:bg-bumblebee-gray-700 text-gray-800 dark:text-bumblebee-gray-300 font-bold py-4 px-6 rounded-lg transition-colors border dark:border-bumblebee-gray-700"
        >
          ← Try Another Job
        </button>
        <button
          onClick={handleAutoFill}
          className="flex-1 bg-indigo-600 hover:bg-indigo-700 dark:bg-bumblebee-yellow dark:hover:bg-bumblebee-gold text-white dark:text-bumblebee-dark font-bold py-4 px-6 rounded-lg transition-colors shadow-lg dark:shadow-bumblebee-yellow/20"
        >
          Auto-Fill Application →
        </button>
      </div>
    </div>
  );
}