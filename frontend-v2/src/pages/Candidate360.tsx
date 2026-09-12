import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Briefcase, GraduationCap, PackagePlus } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { resumesApi } from '../api/resumes';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation } from '../hooks/useDecisionMutation';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { Button } from '../components/ui/Button';
import { 
  ScoreVisualizer, 
  DecisionControlBar, 
  ExtractedSkills, 
  ScreeningAnalysis 
} from '../components/candidate/CandidateComponents';
import { OutreachHistory } from '../components/candidate/OutreachHistory';

export const Candidate360 = () => {
  const { id: jobIdStr, resumeId: resumeIdStr } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  const jobId = parseInt(jobIdStr || '0', 10);
  const resumeId = parseInt(resumeIdStr || '0', 10);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId),
    enabled: !!jobId && !!resumeId,
  });

  const decisionMutation = useDecisionMutation(jobId);
  const addToPool = useAddToTalentPool();

  const handleBack = () => {
    // Navigate back to the previous list with preserved state, or fallback to job detail
    if (location.state?.from) {
      navigate(-1);
    } else {
      navigate(`/jobs/${jobId}`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex-1 p-8">
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          Failed to load candidate details.
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-8 py-4 shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={handleBack}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors focus-ring"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              {data.profile?.name || `Candidate #${resumeId}`}
            </h1>
            <p className="text-sm text-slate-500">
              {data.profile?.email} &bull; {data.profile?.phone || 'No phone provided'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data.filename ? (
            <a 
              href={resumesApi.getResumeFileUrl(resumeId)} 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 hover:text-slate-900 transition-colors focus-ring"
            >
              <ExternalLink className="w-4 h-4" /> Original Resume
            </a>
          ) : (
            <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-400 bg-slate-50 border border-slate-200 rounded-lg cursor-not-allowed" title="Original resume unavailable">
              <ExternalLink className="w-4 h-4 opacity-50" /> Original Resume Unavailable
            </span>
          )}
          <Button
            variant="secondary"
            onClick={() => addToPool.mutate({ resume_id: resumeId, added_from_job_id: jobId })}
            disabled={addToPool.isPending}
            className="flex items-center gap-2"
          >
            <PackagePlus className="w-4 h-4" /> Add to Talent Pool
          </Button>
          <Link to={`/interview/${jobId}/${resumeId}`}>
            <Button>Interview Workspace</Button>
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <DecisionControlBar 
              decision={data.screening?.decision}
              isPending={decisionMutation.isPending}
              onDecision={(d) => decisionMutation.mutate({ resumeId, decision: d })}
            />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Left Column: Profile Data */}
            <div className="xl:col-span-2 space-y-6">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6" id="profile">
                <h2 className="text-lg font-semibold text-slate-900 mb-6">Profile Summary</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                  <div id="experience">
                    <h3 className="text-sm font-medium text-slate-500 mb-3 flex items-center gap-2">
                      <Briefcase className="w-4 h-4" /> Experience
                    </h3>
                    <div className="space-y-4">
                      {Array.isArray(data.profile?.experience) && data.profile.experience.length > 0 ? (
                        data.profile.experience.map((exp: any, i: number) => (
                          <div key={i}>
                            <div className="font-medium text-slate-900">{exp.title || 'Unknown Title'}</div>
                            <div className="text-sm text-slate-600">{exp.company || 'Unknown Company'}</div>
                            <div className="text-xs text-slate-500 mt-1">{exp.dates || ''}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-slate-400 italic">No experience data extracted</div>
                      )}
                    </div>
                  </div>
                  <div id="education">
                    <h3 className="text-sm font-medium text-slate-500 mb-3 flex items-center gap-2">
                      <GraduationCap className="w-4 h-4" /> Education
                    </h3>
                    <div className="space-y-4">
                      {Array.isArray(data.profile?.education) && data.profile.education.length > 0 ? (
                        data.profile.education.map((edu: any, i: number) => (
                          <div key={i}>
                            <div className="font-medium text-slate-900">{edu.degree || 'Unknown Degree'}</div>
                            <div className="text-sm text-slate-600">{edu.institution || 'Unknown Institution'}</div>
                            <div className="text-xs text-slate-500 mt-1">{edu.year || ''}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-slate-400 italic">No education data extracted</div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-100 pt-6" id="skills">
                  <ExtractedSkills profile={data.profile} />
                </div>
              </div>

              <OutreachHistory resumeId={resumeId} />
            </div>

            {/* Right Column: AI Screening */}
            <div className="xl:col-span-1">
              <div className="space-y-6 sticky top-0 pb-8">
                <ScoreVisualizer screening={data.screening} />
                <ScreeningAnalysis screening={data.screening} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
