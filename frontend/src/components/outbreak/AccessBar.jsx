import { useState } from "react";
import { KeyRound, ShieldCheck } from "lucide-react";
import { setAccessKey } from "../../services/outbreakApi";

// The key is typed by the user and kept in sessionStorage only; it is never part of the bundle.
export default function AccessBar({ access, accessKey, onKeyChange }) {
  const [draft, setDraft] = useState("");
  const role = access?.role ?? "public";

  const save = (e) => {
    e.preventDefault();
    setAccessKey(draft.trim());
    onKeyChange(draft.trim());
    setDraft("");
  };
  const clear = () => {
    setAccessKey("");
    onKeyChange("");
  };

  return (
    <div className="mb-6 flex flex-col gap-3 rounded-xl border border-line bg-panel/60 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="flex items-start gap-2 text-ink-2">
        {role === "admin" ? <ShieldCheck className="mt-0.5 size-4 shrink-0 text-leaf" aria-hidden /> : <KeyRound className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />}
        <span>
          {role === "admin"
            ? "Authorised view: exact locations and plantation details are shown, and you can submit data."
            : "Public view: locations are rounded and plantation names, owners and notes are hidden."}
          {access && !access.writes_enabled && " Submitting data is disabled until the server has OUTBREAK_ADMIN_API_KEY set."}
        </span>
      </p>
      {role === "admin" && accessKey ? (
        <button type="button" onClick={clear} className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-ink-2 hover:text-ink">Forget key</button>
      ) : (
        <form onSubmit={save} className="flex shrink-0 gap-2">
          <label htmlFor="access-key" className="sr-only">Access key</label>
          <input
            id="access-key"
            type="password"
            autoComplete="off"
            placeholder="Access key"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="w-40 rounded-lg border border-line bg-ground px-3 py-1.5 text-ink placeholder:text-ink-3 focus:border-leaf focus:outline-none"
          />
          <button type="submit" disabled={!draft.trim()} className="rounded-lg bg-raised px-3 py-1.5 font-medium text-ink hover:bg-line disabled:opacity-50">Unlock</button>
        </form>
      )}
    </div>
  );
}
