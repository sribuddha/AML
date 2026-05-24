import { useState, useRef, type DragEvent } from "react";

interface FileUploaderProps {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
}

export default function FileUploader({ onUpload, accept = ".csv" }: FileUploaderProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      await onUpload(selectedFile);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragOver ? "border-blue-400 bg-blue-50" : "border-slate-300 hover:border-slate-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && setSelectedFile(e.target.files[0])}
        />
        <div className="text-4xl mb-2">📂</div>
        <p className="text-sm text-slate-600">
          {selectedFile ? selectedFile.name : "Drag & drop a CSV file here, or click to browse"}
        </p>
      </div>
      {selectedFile && !uploading && (
        <button
          onClick={handleUpload}
          className="w-full py-2.5 px-4 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 transition-colors"
        >
          Upload {selectedFile.name}
        </button>
      )}
      {uploading && (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          Uploading...
        </div>
      )}
    </div>
  );
}
