export interface LocationSuggestion {
  label: string;
  codes: string[];
  kind: "location" | "airport_code";
}
