export interface MaterialityCheck {
  threshold: number;
  value: number;
  passes: boolean;
}

export function checkMateriality(threshold: number, value: number): MaterialityCheck {
  return {
    threshold,
    value,
    passes: value >= threshold,
  };
}
