import { Link } from "react-router";

export default function NotFound() {
  return (
    <div className="py-24 text-center">
      <h1 className="text-3xl font-semibold">Page not found</h1>
      <p className="mt-3 text-ink-2">This address doesn't match any page in the app.</p>
      <Link to="/" className="mt-6 inline-flex rounded-xl bg-leaf px-4 py-2.5 text-sm font-semibold text-ground hover:bg-leaf/90">
        Go to the dashboard
      </Link>
    </div>
  );
}
