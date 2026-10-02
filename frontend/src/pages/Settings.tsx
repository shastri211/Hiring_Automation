import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Loader2, Users, UserPlus, Lock } from 'lucide-react';
import { useSettings, useUpdateSettings } from '../hooks/useSettings';
import { useEmailTemplates } from '../hooks/useEmails';
import { useAuthUsers, useCreateAuthUser, useUpdateAuthUser } from '../hooks/useAuthUsers';
import { useAuth } from '../hooks/useAuth';
import { useConfirm } from '../hooks/useConfirm';
import { ScreeningThresholdFields } from '../components/settings/ScreeningThresholdFields';
import {
  Alert, Button, ErrorState, Input, Label, Badge, PageHeader, Section, Skeleton, StatusDot,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui';
import type { AppSettingsResponse, AppSettingsUpdate, ApiError, UserResponse } from '../types';

// Threshold fields are modeled as plain strings (see
// ScreeningThresholdFields.tsx for why) — an empty string means "use the
// backend default" and is converted to number|null only in toPatch(), right
// before building the API request.
const numericString = (min: number, max: number) =>
  z.string().refine(
    (v) => v === '' || (Number.isFinite(Number(v)) && Number(v) >= min && Number(v) <= max),
    { message: `Enter a number between ${min} and ${max}, or leave blank to use the default.` }
  );

const schema = z
  .object({
    organization_name: z.string().trim().min(1, 'Organization name is required.').max(255),
    min_candidates_to_screen: numericString(1, 10000),
    max_candidates_to_screen: numericString(1, 10000),
    semantic_gap_threshold: numericString(0, 1),
    auto_email_on_shortlist: z.boolean(),
    shortlist_email_template_id: z.number().nullable(),
    auto_generate_interview_on_shortlist: z.boolean(),
    auto_email_on_interview_scheduled: z.boolean(),
    interview_scheduled_email_template_id: z.number().nullable(),
  })
  .refine(
    (d) =>
      d.min_candidates_to_screen === '' ||
      d.max_candidates_to_screen === '' ||
      Number(d.min_candidates_to_screen) <= Number(d.max_candidates_to_screen),
    { message: 'Minimum must be less than or equal to maximum.', path: ['max_candidates_to_screen'] }
  )
  .refine((d) => !d.auto_email_on_shortlist || d.shortlist_email_template_id != null, {
    message: 'Select a template to enable this automation.',
    path: ['shortlist_email_template_id'],
  })
  .refine((d) => !d.auto_email_on_interview_scheduled || d.interview_scheduled_email_template_id != null, {
    message: 'Select a template to enable this automation.',
    path: ['interview_scheduled_email_template_id'],
  });

type FormValues = z.infer<typeof schema>;

const defaultValues: FormValues = {
  organization_name: '',
  min_candidates_to_screen: '',
  max_candidates_to_screen: '',
  semantic_gap_threshold: '',
  auto_email_on_shortlist: false,
  shortlist_email_template_id: null,
  auto_generate_interview_on_shortlist: false,
  auto_email_on_interview_scheduled: false,
  interview_scheduled_email_template_id: null,
};

function toFormValues(settings: AppSettingsResponse): FormValues {
  return {
    organization_name: settings.organization_name ?? '',
    min_candidates_to_screen: settings.min_candidates_to_screen != null ? String(settings.min_candidates_to_screen) : '',
    max_candidates_to_screen: settings.max_candidates_to_screen != null ? String(settings.max_candidates_to_screen) : '',
    semantic_gap_threshold: settings.semantic_gap_threshold != null ? String(settings.semantic_gap_threshold) : '',
    auto_email_on_shortlist: settings.auto_email_on_shortlist,
    shortlist_email_template_id: settings.shortlist_email_template_id ?? null,
    auto_generate_interview_on_shortlist: settings.auto_generate_interview_on_shortlist,
    auto_email_on_interview_scheduled: settings.auto_email_on_interview_scheduled,
    interview_scheduled_email_template_id: settings.interview_scheduled_email_template_id ?? null,
  };
}

function toPatch(values: FormValues): AppSettingsUpdate {
  return {
    organization_name: values.organization_name.trim(),
    min_candidates_to_screen: values.min_candidates_to_screen === '' ? null : Number(values.min_candidates_to_screen),
    max_candidates_to_screen: values.max_candidates_to_screen === '' ? null : Number(values.max_candidates_to_screen),
    semantic_gap_threshold: values.semantic_gap_threshold === '' ? null : Number(values.semantic_gap_threshold),
    auto_email_on_shortlist: values.auto_email_on_shortlist,
    shortlist_email_template_id: values.shortlist_email_template_id,
    auto_generate_interview_on_shortlist: values.auto_generate_interview_on_shortlist,
    auto_email_on_interview_scheduled: values.auto_email_on_interview_scheduled,
    interview_scheduled_email_template_id: values.interview_scheduled_email_template_id,
  };
}

const inviteSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});
type InviteFormValues = z.infer<typeof inviteSchema>;
const inviteDefaults: InviteFormValues = { name: '', email: '', password: '' };

const formatJoinedDate = (value: string | null) => {
  if (!value) return 'Unknown';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleDateString();
};

const TeamMemberRow = ({ member, isAdmin, isSelf }: { member: UserResponse; isAdmin: boolean; isSelf: boolean }) => {
  const updateMutation = useUpdateAuthUser();
  const confirm = useConfirm();

  const update = (patch: { role?: 'admin' | 'member'; is_active?: boolean }, success: string) => {
    updateMutation.mutate(
      { userId: member.id, patch },
      {
        onSuccess: () => toast.success(success),
        // e.g. 409 last_admin: "An organization must keep at least one active admin."
        onError: (e: ApiError) => toast.error(e.message || 'Failed to update this teammate.'),
      }
    );
  };

  const toggleActive = async () => {
    if (member.is_active) {
      const ok = await confirm({
        title: `Deactivate ${member.name}?`,
        description: isSelf
          ? 'You will lose access immediately.'
          : 'They will no longer be able to sign in. You can reactivate them later.',
        confirmLabel: 'Deactivate',
        danger: true,
      });
      if (!ok) return;
    }
    update(
      { is_active: !member.is_active },
      member.is_active ? `${member.name} deactivated.` : `${member.name} reactivated.`
    );
  };

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
          <span className="truncate">{member.name}</span>
          {isSelf && <span className="text-xs text-[var(--text-tertiary)]">(you)</span>}
          <Badge variant={member.role === 'admin' ? 'primary' : 'neutral'}>{member.role === 'admin' ? 'Admin' : 'Member'}</Badge>
          {!member.is_active && <StatusDot variant="warning" className="text-xs">Deactivated</StatusDot>}
        </p>
        <p className="text-xs text-[var(--text-secondary)] truncate">{member.email}</p>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-[var(--text-tertiary)]">Joined {formatJoinedDate(member.created_at)}</span>
        {isAdmin && (
          <>
            <Select
              value={member.role}
              onValueChange={(v) =>
                update({ role: v as 'admin' | 'member' }, `${member.name} is now ${v === 'admin' ? 'an admin' : 'a member'}.`)
              }
              disabled={updateMutation.isPending}
            >
              <SelectTrigger className="h-8 w-28 text-xs" aria-label={`Role for ${member.name}`}><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="member">Member</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="ghost" size="sm" onClick={toggleActive} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : member.is_active ? 'Deactivate' : 'Reactivate'}
            </Button>
          </>
        )}
      </div>
    </li>
  );
};

const TeamSection = () => {
  const { user, isAdmin } = useAuth();
  const { data: users, isLoading, isError, refetch } = useAuthUsers();
  const createUserMutation = useCreateAuthUser();

  const inviteForm = useForm<InviteFormValues>({ resolver: zodResolver(inviteSchema), defaultValues: inviteDefaults });

  const onInvite = (values: InviteFormValues) => {
    createUserMutation.mutate(values, {
      onSuccess: () => {
        toast.success(`Account created for ${values.name}. Share the temporary password with them directly.`);
        inviteForm.reset(inviteDefaults);
      },
      onError: (e: ApiError) => toast.error(e.message || 'Failed to create the account.'),
    });
  };

  return (
    <Section title="Team" icon={<Users size={13} />} className="space-y-6">

      {isLoading ? (
        <div className="space-y-3" aria-hidden="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
      ) : isError ? (
        <ErrorState className="py-8" title="Failed to load the team list" onRetry={() => refetch()} />
      ) : !users || users.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">No teammates yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--border-light)]">
          {users.map((u) => (
            <TeamMemberRow key={u.id} member={u} isAdmin={isAdmin} isSelf={u.id === user?.id} />
          ))}
        </ul>
      )}

      {isAdmin ? (
        <div className="border-t border-[var(--border-light)] pt-5">
          <h3 className="text-eyebrow mb-1 flex items-center gap-1.5">
            <UserPlus size={13} aria-hidden="true" /> Add teammate
          </h3>
          <p className="text-xs text-[var(--text-secondary)] mb-3">
            Creates a member account with a temporary password. Nothing is emailed - share the password with them
            yourself. They&apos;ll be asked to choose their own password the first time they sign in.
          </p>
          <form
            onSubmit={inviteForm.handleSubmit(onInvite)}
            className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-start"
          >
            <div>
              <Label htmlFor="invite-name">Name</Label>
              <Input id="invite-name" className="mt-1.5" placeholder="Jane Doe" {...inviteForm.register('name')} />
              {inviteForm.formState.errors.name && (
                <p className="text-xs text-[var(--color-danger-600)] mt-1">{inviteForm.formState.errors.name.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="invite-email">Email</Label>
              <Input id="invite-email" type="email" className="mt-1.5" placeholder="jane@company.com" {...inviteForm.register('email')} />
              {inviteForm.formState.errors.email && (
                <p className="text-xs text-[var(--color-danger-600)] mt-1">{inviteForm.formState.errors.email.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="invite-password">Temporary password</Label>
              <Input id="invite-password" type="password" className="mt-1.5" placeholder="••••••••" {...inviteForm.register('password')} />
              {inviteForm.formState.errors.password && (
                <p className="text-xs text-[var(--color-danger-600)] mt-1">{inviteForm.formState.errors.password.message}</p>
              )}
            </div>
            <div className="sm:col-span-3 flex justify-end">
              <Button type="submit" size="sm" disabled={createUserMutation.isPending}>
                {createUserMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : 'Create account'}
              </Button>
            </div>
          </form>
        </div>
      ) : (
        <p className="text-caption border-t border-[var(--border-light)] pt-4">
          Only admins can add or manage teammates.
        </p>
      )}
    </Section>
  );
};

export const Settings = () => {
  const { isAdmin, refreshMe } = useAuth();
  const { data: settings, isLoading, isError, refetch } = useSettings();
  const { data: templates } = useEmailTemplates();
  const updateMutation = useUpdateSettings();

  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues });
  const { register, control, watch, formState } = form;

  useEffect(() => {
    if (settings) {
      form.reset(toFormValues(settings));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  const autoShortlist = watch('auto_email_on_shortlist');
  const autoInterview = watch('auto_email_on_interview_scheduled');

  const onSubmit = (values: FormValues) => {
    updateMutation.mutate(toPatch(values), {
      onSuccess: () => {
        toast.success('Settings saved.');
        form.reset(values);
        // The organization name is shown in the header/sidebar from /auth/me.
        void refreshMe();
      },
      onError: (e: { message?: string }) => toast.error(e.message || 'Failed to save settings.'),
    });
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        className="mb-8"
        title="Settings"
        subtitle="Organization details, screening thresholds, and outreach automation."
      />

      {isLoading ? (
        <div className="space-y-6" aria-hidden="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
      ) : isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load settings" onRetry={() => refetch()} />
        </div>
      ) : (
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
          {!isAdmin && (
            <Alert variant="info" icon={<Lock size={16} />}>
              Company settings are managed by your organization&apos;s admins. You can view them here.
            </Alert>
          )}
          {/* Members get the same view, read-only (the server rejects their changes too). */}
          <fieldset disabled={!isAdmin} className="space-y-8 disabled:opacity-80">
          <Section title="Organization">
            <Label htmlFor="organization_name">Organization Name</Label>
            <Input id="organization_name" placeholder="Acme Inc." className="mt-1.5" {...register('organization_name')} />
            {formState.errors.organization_name && (
              <p className="mt-1 text-xs text-[var(--color-danger-600)]">{formState.errors.organization_name.message}</p>
            )}
          </Section>

          <Section title="AI screening thresholds">
            <ScreeningThresholdFields form={form} />
          </Section>

          <Section title="Outreach automation" className="space-y-6">
            <p className="text-caption -mt-1">
              Outbound email always goes to the candidate's own email address, as extracted from their resume.
              There is no test recipient or redirect.
            </p>

            <div>
              <label className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded"
                  {...register('auto_generate_interview_on_shortlist')}
                />
                <span className="text-sm font-medium text-[var(--text-primary)]">Automatically generate an interview link when shortlisted</span>
              </label>
              <p className="text-caption ml-6">
                Pair this with "Automatically email candidates when an interview is scheduled" below (using a
                template with the <code>{'{{interview_link}}'}</code> variable) to get the full shortlist &rarr;
                link &rarr; email flow with no manual steps.
              </p>
            </div>

            <div>
              <label className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded"
                  {...register('auto_email_on_shortlist')}
                />
                <span className="text-sm font-medium text-[var(--text-primary)]">Automatically email candidates when shortlisted</span>
              </label>
              <Controller
                control={control}
                name="shortlist_email_template_id"
                render={({ field }) => (
                  <Select
                    value={field.value ? String(field.value) : undefined}
                    onValueChange={(v) => field.onChange(Number(v))}
                    disabled={!autoShortlist}
                  >
                    <SelectTrigger><SelectValue placeholder="Choose a template..." /></SelectTrigger>
                    <SelectContent>
                      {templates?.map((t) => <SelectItem key={t.id} value={String(t.id)}>{t.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )}
              />
              {formState.errors.shortlist_email_template_id && (
                <p className="text-xs text-[var(--color-danger-600)] mt-1">{formState.errors.shortlist_email_template_id.message}</p>
              )}
            </div>

            <div>
              <label className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded"
                  {...register('auto_email_on_interview_scheduled')}
                />
                <span className="text-sm font-medium text-[var(--text-primary)]">Automatically email candidates when an interview is scheduled</span>
              </label>
              <Controller
                control={control}
                name="interview_scheduled_email_template_id"
                render={({ field }) => (
                  <Select
                    value={field.value ? String(field.value) : undefined}
                    onValueChange={(v) => field.onChange(Number(v))}
                    disabled={!autoInterview}
                  >
                    <SelectTrigger><SelectValue placeholder="Choose a template..." /></SelectTrigger>
                    <SelectContent>
                      {templates?.map((t) => <SelectItem key={t.id} value={String(t.id)}>{t.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                )}
              />
              {formState.errors.interview_scheduled_email_template_id && (
                <p className="text-xs text-[var(--color-danger-600)] mt-1">{formState.errors.interview_scheduled_email_template_id.message}</p>
              )}
            </div>
          </Section>

          </fieldset>

          {isAdmin && (
            <div className="flex justify-end gap-3">
              <Button type="submit" disabled={!formState.isDirty || updateMutation.isPending}>
                {updateMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : 'Save Settings'}
              </Button>
            </div>
          )}
        </form>
      )}

      <div className="mt-8">
        <TeamSection />
      </div>
    </div>
  );
};
