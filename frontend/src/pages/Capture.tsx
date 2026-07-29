import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ImageRole, type Kind } from "../api/client";
import { BLUR_THRESHOLD, blurScore } from "../lib/blur";
import { enqueueUpload, listQueue, removeFromQueue } from "../lib/uploadQueue";
import { useT, type TranslationKey } from "../i18n";

const COIN_ROLES: ImageRole[] = ["obverse", "reverse", "edge", "detail"];
const NOTE_ROLES: ImageRole[] = ["face", "back", "watermark", "detail"];

export default function Capture() {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [target, setTarget] = useState("new");
  const [kind, setKind] = useState<Kind>("coin");
  const [role, setRole] = useState<ImageRole>("obverse");
  const [status, setStatus] = useState("");
  const [queued, setQueued] = useState(0);

  const recent = useQuery({
    queryKey: ["items", { recent: true }],
    queryFn: () => api.listItems({ page_size: 30, sort: "updated_at" }),
  });

  const roles = kind === "banknote" ? NOTE_ROLES : COIN_ROLES;
  useEffect(() => setRole(roles[0]), [kind]);

  const refreshQueue = () => listQueue().then((rows) => setQueued(rows.length));
  useEffect(() => {
    refreshQueue();
  }, []);

  // Drain whatever was captured while the phone had no connection.
  useEffect(() => {
    const drain = async () => {
      for (const entry of await listQueue()) {
        try {
          await api.uploadImage(entry.itemId, entry.role, entry.blob, entry.filename);
          await removeFromQueue(entry.id);
        } catch {
          break;
        }
      }
      refreshQueue();
      queryClient.invalidateQueries({ queryKey: ["items"] });
    };

    if (navigator.onLine) drain();
    window.addEventListener("online", drain);
    return () => window.removeEventListener("online", drain);
  }, [queryClient]);

  const send = useMutation({
    mutationFn: async (file: File) => {
      const score = await blurScore(file);
      if (score < BLUR_THRESHOLD && !window.confirm(t("capture.blurry"))) return null;

      let itemId = target;
      if (target === "new") {
        const created = await api.createItem({ kind });
        itemId = created.id;
      }

      if (!navigator.onLine) {
        await enqueueUpload({ itemId, role, filename: file.name, blob: file });
        await refreshQueue();
        setStatus(t("capture.queued"));
        return null;
      }

      setStatus(t("capture.uploading"));
      await api.uploadImage(itemId, role, file, file.name);
      return itemId;
    },
    onSuccess: (itemId) => {
      queryClient.invalidateQueries({ queryKey: ["items"] });
      if (itemId) {
        setStatus(t("capture.done"));
        navigate(`/items/${itemId}`);
      }
    },
    onError: () => setStatus(t("common.error")),
  });

  return (
    <div className="stack">
      <h1>{t("capture.title")}</h1>
      <p className="muted small">{t("capture.hint")}</p>

      <div className="card grid">
        <div>
          <label htmlFor="c-target">{t("capture.selectItem")}</label>
          <select id="c-target" value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="new">{t("capture.newItem")}</option>
            {(recent.data?.rows ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {row.title}
              </option>
            ))}
          </select>
        </div>

        {target === "new" && (
          <div>
            <label htmlFor="c-kind">{t("item.kind")}</label>
            <select id="c-kind" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
              <option value="coin">{t("item.kind.coin")}</option>
              <option value="banknote">{t("item.kind.banknote")}</option>
              <option value="token">{t("item.kind.token")}</option>
              <option value="other">{t("item.kind.other")}</option>
            </select>
          </div>
        )}

        <div>
          <label htmlFor="c-role">{t("images.role")}</label>
          <select id="c-role" value={role} onChange={(e) => setRole(e.target.value as ImageRole)}>
            {roles.map((value) => (
              <option key={value} value={value}>
                {t(`images.role.${value}` as TranslationKey)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) send.mutate(file);
          e.target.value = "";
        }}
      />

      <div className="row">
        <button className="primary" disabled={send.isPending} onClick={() => fileInput.current?.click()}>
          {t("capture.take")}
        </button>
        {queued > 0 && <span className="muted small">⏳ {queued}</span>}
      </div>

      {status && <p className="notice">{status}</p>}
    </div>
  );
}
