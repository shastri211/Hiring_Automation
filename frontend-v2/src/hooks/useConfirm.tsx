import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription, Button } from '../components/ui';

export interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface ConfirmContextValue {
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

export const ConfirmProvider = ({ children }: { children: ReactNode }) => {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const [open, setOpen] = useState(false);
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    setOpts(options);
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  const settle = (result: boolean) => {
    setOpen(false);
    resolveRef.current?.(result);
    resolveRef.current = null;
  };

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      <Dialog open={open} onOpenChange={(next) => { if (!next) settle(false); }}>
        <DialogContent className="max-w-md">
          <DialogTitle>{opts?.title}</DialogTitle>
          {opts?.description && <DialogDescription>{opts.description}</DialogDescription>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => settle(false)}>
              {opts?.cancelLabel || 'Cancel'}
            </Button>
            <Button
              onClick={() => settle(true)}
              className={opts?.danger ? 'bg-[var(--color-danger-600)] hover:not-disabled:bg-red-700 border-transparent' : undefined}
            >
              {opts?.confirmLabel || 'Confirm'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
};

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within a ConfirmProvider');
  return ctx.confirm;
}
