interface StatusBadgeProps {
  status?: 'ready' | 'processing' | 'pending' | 'failed' | 'completed' | 'running' | string | null;
  label?: string;
  size?: 'sm' | 'md';
}

export default function StatusBadge({ status, label, size = 'md' }: StatusBadgeProps) {
  const safeStatus = (status || 'pending').toLowerCase();
  const displayLabel = label || safeStatus.toUpperCase();

  const getColors = () => {
    switch (safeStatus) {
      case 'ready':
      case 'completed':
        return {
          dot: 'bg-emerald-400',
          bg: 'bg-emerald-950/30 border-emerald-800/40 text-emerald-300',
        };
      case 'processing':
      case 'running':
      case 'pending':
        return {
          dot: 'bg-cyan-400 animate-status-pulse',
          bg: 'bg-cyan-950/30 border-cyan-800/40 text-cyan-300',
        };
      case 'failed':
        return {
          dot: 'bg-rose-400',
          bg: 'bg-rose-950/30 border-rose-800/40 text-rose-300',
        };
      default:
        return {
          dot: 'bg-zinc-400',
          bg: 'bg-zinc-900 border-zinc-800 text-zinc-400',
        };
    }
  };

  const { dot, bg } = getColors();
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-mono tracking-wider ${padding} ${bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {displayLabel}
    </span>
  );
}
