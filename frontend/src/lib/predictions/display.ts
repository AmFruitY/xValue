/**
 * Presentation-only helpers. The data keep the names exactly as delivered.
 *
 * predicciones_xvalue_final_v1.parquet delivers player_name in lower case and
 * without accents ("yeremy pino"). Until the team exports the original names,
 * the interface capitalises the first letter of each word; it does not add
 * accents and it cannot restore particles such as "de" in "de Jong".
 */
export function displayName(name: string): string {
  return name.replace(/(^|[\s\-'’.])(\p{L})/gu, (_, separator: string, letter: string) => separator + letter.toLocaleUpperCase("es"));
}
