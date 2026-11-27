import type { WireframeResponse } from "../types/wireframe";
import { JsonPreview } from "./JsonPreview";
import { WireframeSection } from "./WireframeSection";

interface Props {
  data: WireframeResponse;
}

export default function WireframeRenderer({ data }: Props) {
  return (
    <div className="wireframe-result">
      <div className="wireframe-canvas" aria-label="Low-fidelity wireframe">
        <div className="wireframe-browser">
          <div className="wireframe-browser-bar" aria-hidden="true"><span /><span /><span /></div>
          <h3 className="wireframe-screen-title">{data.screen_name}</h3>
          <div className="wireframe-sections">{data.sections.map((section, index) => <WireframeSection key={`${section.title}-${index}`} section={section} index={index} />)}</div>
        </div>
      </div>
      <JsonPreview data={data} />
    </div>
  );
}