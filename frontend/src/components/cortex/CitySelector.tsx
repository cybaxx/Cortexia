import { Label } from '@/components/ui/label';
import { CITY_PRESETS } from '@/data/cities';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface CitySelectorProps {
  value: string;
  onChange: (cityId: string) => void;
  disabled?: boolean;
}

/**
 * Target metro for synthetic population layout and report priors.
 */
export const CitySelector = ({ value, onChange, disabled }: CitySelectorProps) => {
  return (
    <div className="space-y-1.5">
      <Label className="font-mono text-[9px] uppercase tracking-wider text-white/85">Target city</Label>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="h-11 rounded-[20px] bg-bg-elevated border-white/[0.08] text-[12px] text-text-primary">
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-bg-surface border-white/[0.1] max-h-64">
          {CITY_PRESETS.map((c) => (
            <SelectItem key={c.id} value={c.id} className="text-[12px]">
              {c.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};
