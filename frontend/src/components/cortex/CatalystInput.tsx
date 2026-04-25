import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';

interface CatalystInputProps {
  text: string;
  onTextChange: (v: string) => void;
  sourceUrl: string;
  onSourceUrlChange: (v: string) => void;
  disabled?: boolean;
  label?: string;
}

/**
 * Primary catalyst capture: paste narrative, article URL, or policy draft.
 */
export const CatalystInput = ({
  text,
  onTextChange,
  sourceUrl,
  onSourceUrlChange,
  disabled,
  label = "Catalyst text",
}: CatalystInputProps) => {
  return (
    <div className="space-y-3">
      <div>
        <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">{label}</Label>
        <p className="text-[10px] text-text-muted/90 mt-0.5 mb-1.5">
          Paste a narrative, drop a long-form article URL in the field below, or write a short policy or comms draft.
        </p>
        <Textarea
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          disabled={disabled}
          className="min-h-[140px] rounded-[24px] border-white/[0.08] bg-bg-elevated/80 text-[12px] leading-relaxed text-text-primary placeholder:text-text-muted/70 resize-y"
          placeholder="Required: at least 12 characters of content to run the network simulation."
        />
      </div>
      <div className="space-y-1.5">
        <Label className="font-mono text-[9px] uppercase tracking-wider text-text-muted">Source URL (optional)</Label>
        <Input
          value={sourceUrl}
          onChange={(e) => onSourceUrlChange(e.target.value)}
          disabled={disabled}
          placeholder="https://"
          className="h-11 rounded-[20px] border-white/[0.08] bg-bg-elevated/80 text-[12px] text-text-primary"
        />
      </div>
    </div>
  );
};
