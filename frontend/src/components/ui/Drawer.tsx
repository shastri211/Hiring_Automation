import { forwardRef, type ComponentPropsWithoutRef, type ElementRef, type HTMLAttributes, type ReactNode } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';

/**
 * Drawer — a right-edge sheet for quick-review surfaces. Built on Radix Dialog
 * (focus trap, Esc, scroll lock, aria) so behavior matches `Dialog`; only the
 * layout differs. Full-screen below `sm`.
 *
 *   <Drawer open onOpenChange>
 *     <DrawerContent>
 *       <DrawerHeader title="…" description="…" />
 *       <DrawerBody>…</DrawerBody>
 *       <DrawerFooter>…</DrawerFooter>
 *     </DrawerContent>
 *   </Drawer>
 */
export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;
export const DrawerClose = DialogPrimitive.Close;

export const DrawerContent = forwardRef<ElementRef<typeof DialogPrimitive.Content>, ComponentPropsWithoutRef<typeof DialogPrimitive.Content>>(
  ({ className, children, ...props }, ref) => (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="overlay-in fixed inset-0 z-50 bg-[var(--bg-overlay)]" />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'drawer-in fixed inset-y-0 right-0 z-50 flex h-dvh w-full flex-col border-l border-[var(--border-strong)] bg-[var(--bg-surface)] shadow-[var(--shadow-lg)] sm:max-w-[34rem]',
          className
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
);
DrawerContent.displayName = 'DrawerContent';

interface DrawerHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode;
  description?: ReactNode;
  /** Optional leading element (avatar, score). */
  leading?: ReactNode;
}

export const DrawerHeader = ({ title, description, leading, className, ...props }: DrawerHeaderProps) => (
  <div className={cn('flex shrink-0 items-start gap-3 border-b border-[var(--border-light)] px-5 py-4', className)} {...props}>
    {leading}
    <div className="min-w-0 flex-1">
      <DialogPrimitive.Title className="text-section-heading truncate">{title}</DialogPrimitive.Title>
      {/* Radix warns when a Dialog has no Description; fall back to an sr-only one. */}
      <DialogPrimitive.Description className={description ? 'text-caption mt-0.5 truncate' : 'sr-only'}>
        {description ?? 'Details panel'}
      </DialogPrimitive.Description>
    </div>
    <DialogPrimitive.Close className="transition-base focus-ring -mr-1.5 shrink-0 rounded p-1.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]">
      <X size={18} />
      <span className="sr-only">Close</span>
    </DialogPrimitive.Close>
  </div>
);

export const DrawerBody = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('min-h-0 flex-1 overflow-y-auto px-5 py-5', className)} {...props} />
);

export const DrawerFooter = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex shrink-0 items-center justify-between gap-3 border-t border-[var(--border-light)] bg-[var(--bg-surface)] px-5 py-3', className)} {...props} />
);
