import LogoImage from "../assets/logo_empresa.png";

interface LogoProps {
  className?: string;
}

export function Logo({ className = "" }: LogoProps) {
  return (
    <img
      src={LogoImage}
      alt="<cliente>nombre_cliente</cliente> Logo"
      className={`h-10 w-auto ${className}`}
    />
  );
}

export default Logo;
