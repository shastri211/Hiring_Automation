import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Link, type LinkProps } from 'react-router-dom';
import { buttonClasses } from './styles';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'md' | 'sm';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={buttonClasses(variant, size, className)}
      {...props}
    />
  )
);

Button.displayName = 'Button';

/** A router <Link> that looks like a Button. Use instead of <Link><Button/></Link>,
 * which nests an interactive element inside another (invalid HTML, double tab stop). */
export const LinkButton = ({ variant = 'primary', size = 'md', className, ...props }: LinkProps & Pick<ButtonProps, 'variant' | 'size'>) => (
  <Link className={buttonClasses(variant, size, className)} {...props} />
);
