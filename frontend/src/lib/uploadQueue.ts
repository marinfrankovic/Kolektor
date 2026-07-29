import type { ImageRole } from "../api/client";

export type QueuedUpload = {
  id: string;
  itemId: string;
  role: ImageRole;
  filename: string;
  blob: Blob;
  queuedAt: number;
};

const DB_NAME = "kolektor";
const STORE = "uploads";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function transact<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>) {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const request = run(tx.objectStore(STORE));
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
        tx.oncomplete = () => db.close();
      }),
  );
}

export async function enqueueUpload(entry: Omit<QueuedUpload, "id" | "queuedAt">) {
  const record: QueuedUpload = {
    ...entry,
    id: crypto.randomUUID(),
    queuedAt: Date.now(),
  };
  await transact("readwrite", (store) => store.put(record));
  return record;
}

export function listQueue(): Promise<QueuedUpload[]> {
  return transact<QueuedUpload[]>("readonly", (store) => store.getAll() as IDBRequest<QueuedUpload[]>);
}

export async function removeFromQueue(id: string) {
  await transact("readwrite", (store) => store.delete(id));
}
