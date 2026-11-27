import type { WireframeSection as WireframeSectionData } from "../types/wireframe";
import { ComponentPlaceholder } from "./ComponentPlaceholder";
interface WireframeSectionProps { section: WireframeSectionData; index: number; }

export function WireframeSection({ section, index }: WireframeSectionProps) {
  return <section className="wireframe-section" aria-label={section.title}><h4 className="wireframe-section-title"><span className="wireframe-section-index">{String(index + 1).padStart(2, "0")}</span>{section.title}</h4><div className="component-list">{section.components.map((component, componentIndex) => <ComponentPlaceholder key={`${component}-${componentIndex}`} label={component} />)}</div></section>;
}