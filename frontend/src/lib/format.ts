function formatCompactNumber(value: number): string {
  const absoluteValue = Math.abs(value);
  const formatter = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  });

  if (absoluteValue >= 1_000_000_000) {
    return `${formatter.format(absoluteValue / 1_000_000_000)}B`;
  }

  if (absoluteValue >= 1_000_000) {
    return `${formatter.format(absoluteValue / 1_000_000)}M`;
  }

  if (absoluteValue >= 1_000) {
    return `${formatter.format(absoluteValue / 1_000)}K`;
  }

  return formatter.format(absoluteValue);
}

export function formatCompactEur(
  value: number,
  options: { signed?: boolean } = {},
): string {
  const sign = value < 0 ? "−" : options.signed && value > 0 ? "+" : "";
  return `${sign}€${formatCompactNumber(value)}`;
}

export function formatSignedPercentage(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
    value,
  );
}
