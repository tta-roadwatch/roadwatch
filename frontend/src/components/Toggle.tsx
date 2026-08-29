interface ToggleProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  /** 켜짐/꺼짐 상태를 글자로도 알린다 — 색만으로 상태를 전달하지 않는다 */
  onText?: string;
  offText?: string;
}

export function Toggle({
  checked,
  onChange,
  label,
  onText = "ON",
  offText = "OFF",
}: ToggleProps) {
  return (
    <button
      type="button"
      className="rw-toggle"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
    >
      <span className="rw-toggle__label">{label}</span>
      <span className="rw-toggle__track" data-on={checked}>
        <span className="rw-toggle__thumb" />
      </span>
      <span className="rw-toggle__label" aria-hidden="true">
        {checked ? onText : offText}
      </span>
    </button>
  );
}
