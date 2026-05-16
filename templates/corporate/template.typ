#set page(margin: {{theme_margin_cm}}cm)
#set text(font: "{{theme_font}}", size: {{theme_size}}pt)

= {{full_name}}
{{email}} | {{phone}} | {{location}}

{{#if summary}}
== Summary
{{summary}}
{{/if}}

{{#if experiences}}
== Work Experience
{{experiences}}
{{/if}}

{{#if skills}}
== Competencies
{{skills}}
{{/if}}

{{#if education}}
== Education
{{education}}
{{/if}}
