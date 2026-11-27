import { useState, type FormEvent } from "react";
import { AppHeader } from "../components/AppHeader";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { RequirementForm } from "../components/RequirementForm";
import WireframeRenderer from "../components/WireframeRenderer";
import { generateWireframe } from "../services/wireframeApi";
import type { WireframeResponse } from "../types/wireframe";

export default function WireframeGenerator() {
  const [requirement, setRequirement] = useState("");
  const [wireframe, setWireframe] = useState<WireframeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!requirement.trim()) {
      setError("Add a requirement before generating a wireframe.");
      return;
    }
    setError(null);
    setWireframe(null);
    setIsLoading(true);
    try {
      setWireframe(await generateWireframe(requirement.trim()));
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "The wireframe could not be generated. Try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setRequirement("");
    setWireframe(null);
    setError(null);
  };

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="workspace-layout">
        <aside className="sidebar" aria-label="Primary navigation">
          <div className="sidebar-label">USE CASES</div>
          <a className="sidebar-link sidebar-link-active" href="#generator" aria-current="page"><span className="sidebar-link-icon" aria-hidden="true">W</span><span>Requirement to Wireframe</span></a>
          <div className="sidebar-footer"><span>Workspace</span><span className="workspace-status"><span aria-hidden="true" /> Ready</span></div>
        </aside>
        <main className="main-content" id="generator">
          <div className="page-heading">
            <nav className="breadcrumbs" aria-label="Breadcrumb"><span>Use cases</span><span aria-hidden="true">/</span><span aria-current="page">Requirement to Wireframe</span></nav>
            <div className="heading-row">
              <div><p className="eyebrow">AI-POWERED DESIGN WORKFLOW</p><h1>Requirement to Wireframe</h1><p className="page-description">Turn a product idea into a clear, low-fidelity screen structure.</p></div>
              <div className="workflow-note"><span className="workflow-note-mark" aria-hidden="true">i</span><div><strong>From brief to blueprint</strong><span>Describe the experience. Review the structure.</span></div></div>
            </div>
          </div>
          <div className="workspace-grid">
            <section className="panel requirement-panel" aria-labelledby="requirement-title">
              <div className="panel-heading"><span className="panel-step" aria-hidden="true">01</span><div><h2 id="requirement-title">Your requirement</h2><p>Describe the screen or experience you need.</p></div></div>
              <RequirementForm requirement={requirement} onRequirementChange={setRequirement} onSubmit={handleGenerate} onClear={handleClear} isLoading={isLoading} />
            </section>
            <section className="panel preview-panel" aria-labelledby="preview-title">
              <div className="panel-heading preview-heading"><span className="panel-step" aria-hidden="true">02</span><div><h2 id="preview-title">Wireframe preview</h2><p>Review the proposed layout and content hierarchy.</p></div>{wireframe && <span className="result-badge"><span aria-hidden="true" /> Ready</span>}</div>
              <div className="preview-body" aria-live="polite" aria-busy={isLoading}>{isLoading && <LoadingState />}{!isLoading && error && <ErrorState message={error} />}{!isLoading && !error && wireframe && <WireframeRenderer data={wireframe} />}{!isLoading && !error && !wireframe && <EmptyState />}</div>
            </section>
          </div>
          <footer className="app-footer"><span>Frontend Copilot <span className="footer-separator">/</span> Product design tools</span><span>Wireframe Generator <span className="footer-version">v1.0</span></span></footer>
        </main>
      </div>
    </div>
  );
}