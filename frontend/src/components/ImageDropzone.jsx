import { useRef, useState } from "react";
import { ImageUp, X } from "lucide-react";
import { MAX_UPLOAD_MB } from "../services/api";

export default function ImageDropzone({ file, previewUrl, onSelect, onClear, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    if (disabled || !files?.length) return;
    onSelect(files[0]);
  };

  if (file && previewUrl) {
    return (
      <div className="flex items-center gap-4 rounded-xl border border-line bg-raised p-3">
        <img src={previewUrl} alt="Selected leaf" className="size-20 shrink-0 rounded-lg object-cover" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink">{file.name}</p>
          <p className="num text-sm text-ink-3">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
            className="mt-1 text-sm font-medium text-leaf hover:underline disabled:opacity-50"
          >
            Choose a different image
          </button>
        </div>
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className="rounded-lg p-2 text-ink-3 hover:bg-panel hover:text-ink disabled:opacity-50"
          aria-label="Remove image"
        >
          <X className="size-4" />
        </button>
        <input ref={inputRef} type="file" accept="image/*" className="sr-only" onChange={(e) => handleFiles(e.target.files)} tabIndex={-1} />
      </div>
    );
  }

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      className={`group relative flex min-h-[240px] cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors focus-within:border-leaf ${
        dragging ? "border-leaf bg-leaf-dim/20" : "border-line-strong bg-ground/40 hover:border-leaf/60"
      }`}
    >
      <span className={`grid size-14 place-items-center rounded-2xl border transition-colors ${dragging ? "border-leaf bg-leaf-dim/40 text-leaf" : "border-line bg-raised text-ink-2 group-hover:text-leaf"}`}>
        <ImageUp className="size-6" aria-hidden />
      </span>
      <span>
        <span className="block font-display text-lg font-semibold text-ink">{dragging ? "Drop the image to upload it" : "Drag a bean leaf photo here"}</span>
        <span className="mt-1 block text-sm text-ink-3">
          or <span className="font-medium text-leaf">browse your files</span>. JPG, PNG, WEBP, BMP or TIFF, up to {MAX_UPLOAD_MB} MB.
        </span>
      </span>
      <span className="max-w-sm text-xs leading-relaxed text-ink-3">
        Works best with one leaf filling most of the frame, in daylight, like the field photos the model was trained on.
      </span>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
        aria-label="Upload a bean leaf image"
      />
    </label>
  );
}
