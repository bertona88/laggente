import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export const ArrowUpRightIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M7 17 17 7M8 7h9v9" /></IconBase>
);
export const ArrowRightIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M5 12h14M14 7l5 5-5 5" /></IconBase>
);
export const ArrowLeftIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M19 12H5m5 5-5-5 5-5" /></IconBase>
);
export const SendIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m4 4 17 8-17 8 3-8-3-8Z" /><path d="M7 12h14" /></IconBase>
);
export const MicIcon = (props: IconProps) => (
  <IconBase {...props}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" /></IconBase>
);
export const ImageIcon = (props: IconProps) => (
  <IconBase {...props}><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9" r="1.5" /><path d="m21 15-5-5L5 20" /></IconBase>
);
export const SparkIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m12 3 .8 3.2A6 6 0 0 0 17.2 11l2.8 1-2.8 1a6 6 0 0 0-4.4 4.8L12 21l-.8-3.2A6 6 0 0 0 6.8 13L4 12l2.8-1a6 6 0 0 0 4.4-4.8L12 3Z" /></IconBase>
);
export const ConversationIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M21 13a7 7 0 0 1-7 7H7l-4 2 1.4-4.2A8 8 0 1 1 21 13Z" /></IconBase>
);
export const StudioIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M4 20V9l8-5 8 5v11" /><path d="M8 20v-7h8v7M2 20h20" /></IconBase>
);
export const LayersIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></IconBase>
);
export const InviteIcon = (props: IconProps) => (
  <IconBase {...props}><circle cx="9" cy="8" r="4" /><path d="M3 21v-2a6 6 0 0 1 6-6c2 0 3.7.8 4.8 2M18 8v8M14 12h8" /></IconBase>
);
export const EditIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4L16.5 3.5Z" /></IconBase>
);
export const PauseIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M8 5v14M16 5v14" /></IconBase>
);
export const PlayIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m8 5 11 7-11 7V5Z" /></IconBase>
);
export const CloseIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M6 6l12 12M18 6 6 18" /></IconBase>
);
export const MenuIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M4 7h16M4 12h16M4 17h16" /></IconBase>
);
export const CheckIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m5 12 4 4L19 6" /></IconBase>
);
export const ChevronRightIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m9 18 6-6-6-6" /></IconBase>
);
export const ChevronDownIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m6 9 6 6 6-6" /></IconBase>
);
export const ExternalIcon = ArrowUpRightIcon;
export const LogOutIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M10 17l5-5-5-5M15 12H3M15 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" /></IconBase>
);
export const MoreIcon = (props: IconProps) => (
  <IconBase {...props}><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></IconBase>
);
export const AlertIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.6 2.5 17a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0Z" /></IconBase>
);
export const LockIcon = (props: IconProps) => (
  <IconBase {...props}><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></IconBase>
);
