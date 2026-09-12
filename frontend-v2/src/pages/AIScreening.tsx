import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Loader2, Brain } from 'lucide-react';
import { useSettings, useUpdateSettings } from '../hooks/useSettings';
import { ScreeningThresholdFields, type ThresholdFormValues } from '../components/settings/ScreeningThresholdFields';
import { Button } from '../components/ui';
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
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <Brain className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">AI Screening Configuration</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Tune the adaptive semantic screening gate. Leave any field blank to use the backend's environment default.
          </p>
        </div>
      </div>

      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-6">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="text-center py-12">
            <p className="text-[var(--color-danger-600)] mb-4">Failed to load current settings.</p>
            <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
          </div>
        ) : (
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <ScreeningThresholdFields form={form} />
            <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border-light)]">
              <Button
                type="button"
                variant="secondary"
                disabled={!form.formState.isDirty || updateMutation.isPending}
                onClick={() => settings && form.reset(toFormValues(settings))}
              >
                Discard Changes
              </Button>
              <Button type="submit" disabled={!form.formState.isDirty || updateMutation.isPending}>
                {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Thresholds'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
