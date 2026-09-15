import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Loader2, Settings as SettingsIcon, Users, UserPlus } from 'lucide-react';
import { useSettings, useUpdateSettings } from '../hooks/useSettings';
import { useEmailTemplates } from '../hooks/useEmails';
import { useAuthUsers, useCreateAuthUser } from '../hooks/useAuthUsers';
import { ScreeningThresholdFields } from '../components/settings/ScreeningThresholdFields';
import {
  Button, Input, Label, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui';
import type { AppSettingsResponse, AppSettingsUpdate, ApiError } from '../types';

// Threshold + org_name fields are modeled as plain strings (see
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
    org_name: z.string(),
    min_candidates_to_screen: numericString(1, 10000),
    max_candidates_to_screen: numericString(1, 10000),
    semantic_gap_threshold: numericString(0, 1),
    auto_email_on_shortlist: z.boolean(),
    shortlist_email_template_id: z.number().nullable(),
    auto_email_on_interview_scheduled: z.boolean(),
    interview_scheduled_email_template_id: z.number().nullable(),
    email_test_allowlist: z.string(),
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
  })
  .refine(
    (d) => {
      const entries = d.email_test_allowlist.split(',').map((e) => e.trim()).filter(Boolean);
      return entries.every((e) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e));
    },
    { message: 'Enter valid, comma-separated email addresses.', path: ['email_test_allowlist'] }
  );

type FormValues = z.infer<typeof schema>;

const defaultValues: FormValues = {
  org_name: '',
  min_candidates_to_screen: '',
  max_candidates_to_screen: '',
  semantic_gap_threshold: '',
  auto_email_on_shortlist: false,
  shortlist_email_template_id: null,
  auto_email_on_interview_scheduled: false,
  interview_scheduled_email_template_id: null,
  email_test_allowlist: '',
};

function toFormValues(settings: AppSettingsResponse): FormValues {
  return {
    org_name: settings.org_name ?? '',
    min_candidates_to_screen: settings.min_candidates_to_screen != null ? String(settings.min_candidates_to_screen) : '',
    max_candidates_to_screen: settings.max_candidates_to_screen != null ? String(settings.max_candidates_to_screen) : '',
    semantic_gap_threshold: settings.semantic_gap_threshold != null ? String(settings.semantic_gap_threshold) : '',
    auto_email_on_shortlist: settings.auto_email_on_shortlist,
    shortlist_email_template_id: settings.shortlist_email_template_id ?? null,
    auto_email_on_interview_scheduled: settings.auto_email_on_interview_scheduled,
    interview_scheduled_email_template_id: settings.interview_scheduled_email_template_id ?? null,
    email_test_allowlist: settings.email_test_allowlist ?? '',
  };
}

function toPatch(values: FormValues): AppSettingsUpdate {
  return {
    org_name: values.org_name === '' ? null : values.org_name,
    min_candidates_to_screen: values.min_candidates_to_screen === '' ? null : Number(values.min_candidates_to_screen),
    max_candidates_to_screen: values.max_candidates_to_screen === '' ? null : Number(values.max_candidates_to_screen),
    semantic_gap_threshold: values.semantic_gap_threshold === '' ? null : Number(values.semantic_gap_threshold),
    auto_email_on_shortlist: values.auto_email_on_shortlist,
    shortlist_email_template_id: values.shortlist_email_template_id,
    auto_email_on_interview_scheduled: values.auto_email_on_interview_scheduled,
    interview_scheduled_email_template_id: values.interview_scheduled_email_template_id,
    email_test_allowlist: values.email_test_allowlist === '' ? null : values.email_test_allowlist,
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

const TeamSection = () => {
  const { data: users, isLoading, isError, refetch } = useAuthUsers();
  const createUserMutation = useCreateAuthUser();

  const inviteForm = useForm<InviteFormValues>({ resolver: zodResolver(inviteSchema), defaultValues: inviteDefaults });

  const onInvite = (values: InviteFormValues) => {
    createUserMutation.mutate(values, {
      onSuccess: () => {
        toast.success(`Invited ${values.name}.`);
        inviteForm.reset(inviteDefaults);
      },
      onError: (e: ApiError) => toast.error(e.message || 'Failed to create the account.'),
    });
  };

  return (
    <section className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Users className="w-4 h-4 text-[var(--text-secondary)]" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Team</h2>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-[var(--color-primary-500)]" /></div>
      ) : isError ? (
        <div className="text-center py-8">
          <p className="text-sm text-[var(--color-danger-600)] mb-3">Failed to load the team list.</p>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>Retry</Button>
        </div>
      ) : !users || users.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">No teammates yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--border-light)]">
          {users.map((u) => (
            <li key={u.id} className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)]">{u.name}</p>
                <p className="text-xs text-[var(--text-secondary)]">{u.email}</p>
              </div>
              <span className="text-xs text-[var(--text-tertiary)]">Joined {formatJoinedDate(u.created_at)}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="border-t border-[var(--border-light)] pt-5">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-3 flex items-center gap-1.5">
          <UserPlus className="w-3.5 h-3.5" /> Invite teammate
        </h3>
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
              {createUserMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send invite'}
            </Button>
          </div>
        </form>
      </div>
    </section>
  );
};

export const Settings = () => {
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
      },
      onError: (e: { message?: string }) => toast.error(e.message || 'Failed to save settings.'),
    });
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <SettingsIcon className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Settings</h1>
          <p className="text-sm text-[var(--text-secondary)]">Organization details, screening thresholds, and outreach automation.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" /></div>
      ) : isError ? (
        <div className="text-center py-12 bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl">
          <p className="text-[var(--color-danger-600)] mb-4">Failed to load settings.</p>
          <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
        </div>
      ) : (
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
          <section className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-6">
            <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">Organization</h2>
            <Label htmlFor="org_name">Organization Name</Label>
            <Input id="org_name" placeholder="Acme Inc." className="mt-1.5" {...register('org_name')} />
          </section>

          <section className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-6">
            <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">AI Screening Thresholds</h2>
            <ScreeningThresholdFields form={form} />
          </section>

          <section className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-6 space-y-6">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Outreach Automation</h2>

            <div>
              <Label htmlFor="email_test_allowlist">Test email allowlist</Label>
              <p className="text-xs text-[var(--text-secondary)] mt-1 mb-2">
                While candidate data is for testing only, outbound mail is blocked for every recipient
                except the addresses listed here. Add a real address you control (comma-separated for
                multiple) whenever you want to test a send; anything not listed is recorded as
                "Blocked" in Outreach instead of actually being sent.
              </p>
              <Textarea
                id="email_test_allowlist"
                rows={2}
                placeholder="you@example.com, teammate@example.com"
                {...register('email_test_allowlist')}
              />
              {formState.errors.email_test_allowlist && (
                <p className="text-xs text-[var(--color-danger-600)] mt-1">{formState.errors.email_test_allowlist.message}</p>
              )}
            </div>

            <div>
              <label className="flex items-center gap-2 mb-2">
                <input
                  type="checkbox"
                  className="rounded border-[var(--border-strong)] text-[var(--color-primary-600)] focus:ring-[var(--color-primary-500)]"
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
                  className="rounded border-[var(--border-strong)] text-[var(--color-primary-600)] focus:ring-[var(--color-primary-500)]"
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
          </section>

          <div className="flex justify-end gap-3">
            <Button type="submit" disabled={!formState.isDirty || updateMutation.isPending}>
              {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Settings'}
            </Button>
          </div>
        </form>
      )}

      <div className="mt-8">
        <TeamSection />
      </div>
    </div>
  );
};
