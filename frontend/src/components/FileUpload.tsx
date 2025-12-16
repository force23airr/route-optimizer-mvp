import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isLoading?: boolean;
}

export default function FileUpload({ onFileSelect, isLoading }: FileUploadProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0]);
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
    },
    multiple: false,
    disabled: isLoading,
  });

  return (
    <div
      {...getRootProps()}
      style={{
        border: '2px dashed #ccc',
        borderRadius: '8px',
        padding: '40px 20px',
        textAlign: 'center',
        cursor: isLoading ? 'not-allowed' : 'pointer',
        backgroundColor: isDragActive ? '#f0f7ff' : '#fafafa',
        transition: 'all 0.2s ease',
        opacity: isLoading ? 0.6 : 1,
      }}
    >
      <input {...getInputProps()} />
      {isLoading ? (
        <p>Processing...</p>
      ) : isDragActive ? (
        <p>Drop the CSV file here...</p>
      ) : (
        <div>
          <p style={{ marginBottom: '8px', fontSize: '16px' }}>
            Drag & drop a CSV file here, or click to select
          </p>
          <p style={{ color: '#666', fontSize: '14px' }}>
            Expected columns: id, latitude, longitude, address, demand, time_window_start, time_window_end
          </p>
        </div>
      )}
    </div>
  );
}
