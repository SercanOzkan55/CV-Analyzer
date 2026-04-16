import React, { useState } from 'react';

export default function BlogPostForm({ onPost }) {
  const [text, setText] = useState('');
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);

  function handleImageChange(e) {
    const file = e.target.files[0];
    if (file) {
      setImage(file);
      setPreview(URL.createObjectURL(file));
    } else {
      setImage(null);
      setPreview(null);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!text.trim() && !image) return;
    onPost({ text, image });
    setText('');
    setImage(null);
    setPreview(null);
  }


    return (
      <form className="blog-post-form" onSubmit={handleSubmit}>
        <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
          {/* Avatar placeholder */}
          <div style={{width:32,height:32,borderRadius:'50%',background:'#e3e3e3',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:700,fontSize:'1.1rem'}}>P</div>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Teknolojik gelişme veya paylaşım..."
            rows={3}
            style={{flex:1}}
          />
        </div>
        <div className="blog-post-form-actions">
          <input type="file" accept="image/*" onChange={handleImageChange} />
          {preview && <img src={preview} alt="Önizleme" className="blog-post-preview" />}
          <button type="submit" style={{marginLeft:'auto'}}>Paylaş</button>
        </div>
      </form>
    );
}
