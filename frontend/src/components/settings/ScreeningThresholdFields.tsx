import type { UseFormReturn } from 'react-hook-form';
import { Input, Label, Badge, Button } from '../ui';

/**
 * Shared by AIScreening.tsx and Settings.tsx so the "override vs default" UI
 * for the three screening threshold fields isn't duplicated. Both forms must
 * use exactly these field names.
 *
 * Fields are modeled as plain strings (not `number | null`) because that's
 * what a native `<input>` registered via react-hook-form actually produces,
 * and it keeps zodResolver's generic inference simple (no `z.preprocess`
 * input/output type mismatch). An empty string means "use the backend
 * default"; the numeric conversion to `number | null` happens once, in each
 * page's onSubmit, right before building the API patch.
 */
export interface ThresholdFormValues {
  min_candidates_to_screen: string;
  max_candidates_to_screen: string;
  semantic_gap_threshold: string;
}

interface FieldConfig {
  name: keyof ThresholdFormValues;
  label: string;
  helpText: string;
  step: string;
  min: number;
  max?: number;
}

const FIELDS: FieldConfig[] = [
  {
    name: 'min_candidates_to_screen',
    label: 'Minimum candidates to screen',
    helpText: 'Floor for the adaptive semantic screening gate. Leave blank to use the backend environment default.',
    step: '1',
    min: 1,
  },
  {
    name: 'max_candidates_to_screen',
    label: 'Maximum candidates to screen',
    helpText: 'Ceiling for the adaptive semantic screening gate. Leave blank to use the backend environment default.',
    step: '1',
    min: 1,
  },
  {
    name: 'semantic_gap_threshold',
    label: 'Semantic gap threshold',
    helpText: 'Score-gap (0-1) the adaptive gate uses to decide when to stop screening early. Leave blank to use the backend environment default.',
    step: '0.01',
    min: 0,
    max: 1,
  },
];

function isCustomValue(value: unknown): boolean {
  return value !== null && value !== undefined && value !== '';
}

export function ScreeningThresholdFields<T extends ThresholdFormValues>({ form }: { form: UseFormReturn<T> }) {
  const { register, watch, setValue } = form;

  return (
    <div className="space-y-6">
      {FIELDS.map((field) => {
        const value = watch(field.name as any);
        const custom = isCustomValue(value);
        return (
          <div key={field.name}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
              <Label htmlFor={field.name}>{field.label}</Label>
              <div className="flex items-center gap-2">
                <Badge variant={custom ? 'primary' : 'neutral'}>{custom ? 'Custom' : 'Using default'}</Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={!custom}
                  onClick={() => setValue(field.name as any, '' as any, { shouldDirty: true, shouldValidate: true })}
                >
                  Reset to default
                </Button>
              </div>
            </div>
            <Input
              id={field.name}
              type="number"
              step={field.step}
              min={field.min}
              max={field.max}
              placeholder="Using environment default"
              {...register(field.name as any)}
            />
            <p className="text-xs text-[var(--text-tertiary)] mt-1">{field.helpText}</p>
          </div>
        );
      })}
    </div>
  );
}
