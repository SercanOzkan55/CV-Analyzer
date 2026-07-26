import React, { useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import { getAvatarColor, getInitials } from "../blogStore";

export default function CommentBox({
  onSubmit,
  commentCount,
  disabled = false,
}: {
  onSubmit: (text: string) => boolean | void | Promise<boolean | void>;
  commentCount?: number;
  disabled?: boolean;
}) {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const userName =
    (user as any)?.user_metadata?.full_name ||
    (user as any)?.email?.split("@")[0] ||
    "A";

  async function handleSubmit() {
    if (!text.trim() || submitting) return;
    setSubmitting(true);
    const accepted = await onSubmit(text.trim());
    if (accepted !== false) setText("");
    setSubmitting(false);
  }

  return (
    <div className="blog-comment-box">
      <div className="blog-comment-box-header">
        <MessageCircle size={20} style={{ color: "var(--color-accent)" }} />
        <h3 className="blog-comment-box-title">
          {t("blog.comments_title")}
          {commentCount !== undefined && (
            <span style={{ color: "var(--color-text-muted)", fontWeight: 400, fontSize: "0.9em", marginLeft: "6px" }}>
              ({commentCount})
            </span>
          )}
        </h3>
      </div>

      <div style={{ display: "flex", gap: "12px", position: "relative", zIndex: 1 }}>
        {/* Avatar */}
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: getAvatarColor(userName),
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontSize: "0.82rem",
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {getInitials(userName) || userName[0]?.toUpperCase() || "A"}
        </div>

        <div style={{ flex: 1 }}>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder={t("blog.comment_placeholder")}
            rows={3}
            className="blog-comment-textarea"
            disabled={disabled}
          />
          <div className="blog-comment-footer">
            <span className="blog-comment-hint">{disabled ? t("blog.sign_in_to_comment") : t("blog.comment_hint")}</span>
            <button
              onClick={handleSubmit}
              disabled={disabled || submitting || !text.trim()}
              className="btn-primary btn-sm"
              style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              <Send size={14} />
              {t("blog.submit_comment")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
