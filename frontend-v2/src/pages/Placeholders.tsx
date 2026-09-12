
import { useParams } from 'react-router-dom';
import { EmptyState } from '../components/ui';

export const PlaceHolderPage = ({ title }: { title: string }) => {
  const params = useParams();
  
  return (
    <div>
      <div className="p-8">
        <h1 className="text-2xl font-bold mb-4">{title}</h1>
        <p className="text-slate-600">Route params: {JSON.stringify(params)}</p>
      </div>
      <EmptyState 
        title={`${title} (Coming Soon)`}
        description="This module is planned for a future release and is currently under construction."
      />
    </div>
  );
};

export const GlobalCandidates = () => <PlaceHolderPage title="All Candidates" />;
export const GlobalInterviews = () => <PlaceHolderPage title="All Interviews" />;
export const TalentPool = () => <PlaceHolderPage title="Talent Pool" />;
export const Outreach = () => <PlaceHolderPage title="Email & Outreach" />;
export const AIScreening = () => <PlaceHolderPage title="AI Screening Config" />;
export const InterviewAnalysis = () => <PlaceHolderPage title="Interview Analysis" />;
export const Analytics = () => <PlaceHolderPage title="Analytics Dashboard" />;
export const Integrations = () => <PlaceHolderPage title="System Integrations" />;
export const Settings = () => <PlaceHolderPage title="Settings" />;
