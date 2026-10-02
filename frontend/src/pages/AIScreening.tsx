import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useSettings, useUpdateSettings } from '../hooks/useSettings';
import { ScreeningThresholdFields, type ThresholdFormValues } from '../components/settings/ScreeningThresholdFields';
import { Button, ErrorState, PageHeader, Section, Skeleton } from '../components/ui';
import type { AppSettingsUpdate } from '../types';

const numericString = (min: number, max: number) =>
  z.string().refine(
    (v) => v === '' || (Number.isFinite(Number(v)) && Number(v) >= min && Number(v) <= max),
    { message: `Enter a number between ${min} and ${max}, or leave blank to use the default.` }
  );

const schema = z
  .object({
    min_candidates_to_screen: numericString(1, 10000),
    max_candidates_to_screen: numericString(1, 10000),
    semantic_gap_threshold: numericString(0, 1),
  })
  .refine(
    (d) =>
      d.min_candidates_to_screen === '' ||
      d.max_candidates_to_screen === '' ||
      Number(d.min_candidates_to_screen) <= Number(d.max_candidates_to_screen),
    { message: 'Minimum must be less than or equal to maximum.', path: ['max_candidates_to_screen'] }
  );

type FormValues = ThresholdFormValues;

function toFormValues(settings: { min_candidates_to_screen?: number | null; max_candidates_to_screen?: number | null; semantic_gap_threshold?: number | null }): FormValues {
  return {
    min_candidates_to_screen: settings.min_candidates_to_screen != null ? String(settings.min_candidates_to_screen) : '',
    max_candidates_to_screen: settings.max_candidates_to_screen != null ? String(settings.max_candidates_to_screen) : '',
    semantic_gap_threshold: settings.semantic_gap_threshold != null ? String(settings.semantic_gap_threshold) : '',
  };
}

function toPatch(values: FormValues): AppSettingsUpdate {
  return {
    min_candidates_to_screen: values.min_candidates_to_screen === '' ? null : Number(values.min_candidates_to_screen),
    max_candidates_to_screen: values.max_candidates_to_screen === '' ? null : Number(values.max_candidates_to_screen),
    semantic_gap_threshold: values.semantic_gap_threshold === '' ? null : Number(values.semantic_gap_threshold),
  };
}

export const AIScreening = () => {
  const { data: settings, isLoading, isError, refetch } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      min_candidates_to_screen: '',
      max_candidates_to_screen: '',
      semantic_gap_threshold: '',
    },
  });

  useEffect(() => {
    if (settings) {
      form.reset(toFormValues(settings));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  const onSubmit = (values: FormValues) => {
    updateMutation.mutate(toPatch(values), {
      onSuccess: () => {
        toast.success('AI screening thresholds updated.');
        form.reset(values);
      },
      onError: (e: { message?: string }) => toast.error(e.message || 'Failed to save thresholds.'),
    });
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        className="mb-6"
        title="AI screening configuration"
        subtitle="Tune the adaptive semantic screening gate. Leave any field blank to use the backend's environment default."
      />

      {isLoading ? (
        <div className="space-y-6" aria-hidden="true">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load current settings" onRetry={() => refetch()} />
        </div>
      ) : (
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
          <Section title="Semantic screening thresholds">
            <ScreeningThresholdFields form={form} />
          </Section>
          <div className="flex justify-end gap-2 border-t border-[var(--border-light)] pt-5">
            <Button
              type="button"
              variant="secondary"
              disabled={!form.formState.isDirty || updateMutation.isPending}
              onClick={() => settings && form.reset(toFormValues(settings))}
            >
              Discard changes
            </Button>
            <Button type="submit" disabled={!form.formState.isDirty || updateMutation.isPending}>
              {updateMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : 'Save thresholds'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
};
