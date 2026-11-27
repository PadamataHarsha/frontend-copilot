import { ArrowUpRight, FileText, RotateCcw, Sparkles } from "lucide-react";
import type { FormEvent } from "react";

interface RequirementFormProps { requirement: string; onRequirementChange: (value: string) => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onClear: () => void; isLoading: boolean; }
const examples = ["Leave management portal", "Customer registration", "Fund transfer", "E-commerce checkout"];

export function RequirementForm({ requirement, onRequirementChange, onSubmit, onClear, isLoading }: RequirementFormProps) {
  return <form className="requirement-form" onSubmit={onSubmit}>
    <label className="textarea-label" htmlFor="requirement">Describe your product screen</label>
    <textarea id="requirement" className="requirement-textarea" value={requirement} onChange={(event) => onRequirementChange(event.target.value)} maxLength={2000} placeholder="Example: Build a leave management portal where employees can request time off, check their balance, and track approvals." aria-describedby="requirement-count" required />
    <div className="textarea-meta" id="requirement-count"><span>Include users, key actions, and important information.</span><span>{requirement.length}/2000</span></div>
    <div className="examples-block"><p className="examples-label"><FileText size={14} aria-hidden="true" /> Quick starts</p><div className="example-grid">{examples.map((example) => <button className="example-button" key={example} type="button" onClick={() => onRequirementChange(`Design a ${example.toLowerCase()} screen with clear navigation, key information, and a straightforward primary action.`)}><span>{example}</span><ArrowUpRight size={13} aria-hidden="true" /></button>)}</div></div>
    <div className="form-actions"><button className="button button-primary" type="submit" disabled={isLoading}><Sparkles size={15} aria-hidden="true" />{isLoading ? "Generating..." : "Generate wireframe"}</button><button className="button button-secondary" type="button" onClick={onClear} disabled={isLoading || !requirement}><RotateCcw size={14} aria-hidden="true" /> Clear</button></div>
  </form>;
}