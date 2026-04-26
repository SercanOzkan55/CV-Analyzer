import React, { useState } from "react";
import { Reply, ThumbsUp } from "lucide-react";
import { useLanguage } from "../../i18n/LanguageContext";
import { formatDate, getAvatarColor, getInitials, type Comment } from "../blogStore";

function CommentItem({
  comment,
  onReply,
  onLike,
}: {
  comment: Comment;
  onReply: (commentId: string, text: string) => void;
  onLike: (commentId: string) => void;
}) {
  const [showReply, setShowReply] = useState(false);
  const [replyText, setReplyText] = useState("");
  const { t } = useLanguage();

  function handleReply() {
    if (!replyText.trim()) return;
    onReply(comment.id, replyText.trim());
    setReplyText("");
    setShowReply(false);
  }

  return (
    <div className="blog-comment-item">
      {/* Avatar */}
      <div
        style={{
          width: 38,
          height: 38,
          borderRadius: "50%",
          background: getAvatarColor(comment.author.name),
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontSize: "0.78rem",
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        {getInitials(comment.author.name) || "?"}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Bubble */}
        <div className="blog-comment-bubble">
          <div className="blog-comment-author-row">
            <div>
              <div className="blog-comment-name">{comment.author.name}</div>
              <div className="blog-comment-role">
                {comment.author.role === "recruiter"
                  ? t("blog.role_recruiter")
                  : comment.author.plan === "premium"
                  ? t("blog.role_premium")
                  : t("blog.role_member")}
              </div>
            </div>
            <span className="blog-comment-date">{formatDate(comment.createdAt, t("blog.months"))}</span>
          </div>
          <p className="blog-comment-text">{comment.text}</p>
        </div>

        {/* Actions */}
        <div className="blog-comment-actions">
          <button onClick={() => onLike(comment.id)} className="blog-comment-action-btn">
            <ThumbsUp size={13} />
            <span>{comment.likes.length}</span>
          </button>
          <button onClick={() => setShowReply(!showReply)} className="blog-comment-action-btn">
            <Reply size={13} />
            <span>{t("blog.reply")}</span>
          </button>
        </div>

        {/* Reply form */}
        {showReply && (
          <div className="blog-reply-form">
            <input
              value={replyText}
              onChange={e => setReplyText(e.target.value)}
              placeholder={t("blog.reply_placeholder")}
              className="blog-reply-input"
              onKeyDown={e => e.key === "Enter" && handleReply()}
            />
            <button
              onClick={handleReply}
              className="btn-primary btn-sm"
              style={{ whiteSpace: "nowrap" }}
            >
              {t("blog.send_reply")}
            </button>
            <button
              onClick={() => setShowReply(false)}
              className="btn-outline btn-sm"
              style={{ whiteSpace: "nowrap" }}
            >
              {t("blog.cancel")}
            </button>
          </div>
        )}

        {/* Nested replies */}
        {comment.replies.length > 0 && (
          <div className="blog-replies">
            {comment.replies.map(reply => (
              <div key={reply.id} className="blog-reply-item">
                <div
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: "50%",
                    background: getAvatarColor(reply.author.name),
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {getInitials(reply.author.name) || "?"}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="blog-reply-bubble">
                    <div className="blog-comment-author-row">
                      <div>
                        <div className="blog-comment-name" style={{ fontSize: "0.82rem" }}>
                          {reply.author.name}
                        </div>
                        <div className="blog-comment-role">
                          {reply.author.role === "recruiter"
                            ? t("blog.role_recruiter")
                            : reply.author.plan === "premium"
                            ? t("blog.role_premium")
                            : t("blog.role_member")}
                        </div>
                      </div>
                      <span className="blog-comment-date">
                        {formatDate(reply.createdAt, t("blog.months"))}
                      </span>
                    </div>
                    <p className="blog-comment-text" style={{ fontSize: "0.85rem" }}>
                      {reply.text}
                    </p>
                  </div>
                  <div className="blog-comment-actions">
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "4px",
                        fontSize: "0.75rem",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      <ThumbsUp size={11} />
                      {reply.likes.length}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CommentList({
  comments,
  onReply,
  onLike,
}: {
  comments: Comment[];
  onReply: (commentId: string, text: string) => void;
  onLike: (commentId: string) => void;
}) {
  const { t } = useLanguage();
  const [visibleCount, setVisibleCount] = useState(5);
  const visible = comments.slice(0, visibleCount);
  const hasMore = comments.length > visibleCount;

  if (comments.length === 0) {
    return (
      <p style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "24px 0", fontSize: "0.9rem" }}>
        {t("blog.no_comments")}
      </p>
    );
  }

  return (
    <div className="blog-comments-section">
      {visible.map(comment => (
        <CommentItem key={comment.id} comment={comment} onReply={onReply} onLike={onLike} />
      ))}
      {hasMore && (
        <button
          onClick={() => setVisibleCount(v => v + 5)}
          className="blog-load-more-btn"
        >
          {t("blog.load_more_comments")}
        </button>
      )}
    </div>
  );
}
