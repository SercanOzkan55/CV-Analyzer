export default function CommentBox() {
  return (
    <div className="bg-[#111a2e] p-4 rounded-xl">
      <textarea className="w-full bg-[#0b1220] p-3 rounded" placeholder="Yorum yaz" />
      <button className="mt-3 bg-cyan-500 px-4 py-2 rounded">Yorum yap</button>
    </div>
  );
}
