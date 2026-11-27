import type { WireframeResponse, WireframeSection } from "../types/wireframe";
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const isWireframeSection = (value: unknown): value is WireframeSection => isRecord(value) && typeof value.title === "string" && Array.isArray(value.components) && value.components.every((component: unknown) => typeof component === "string");

export function validateWireframe(value: unknown): WireframeResponse {
  if (!isRecord(value) || typeof value.screen_name !== "string" || !Array.isArray(value.sections) || !value.sections.every(isWireframeSection)) throw new Error("The server returned a response in an unexpected format.");
  return { screen_name: value.screen_name, sections: value.sections };
}