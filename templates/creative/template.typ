#set page(margin: {{theme_margin_cm}}cm)
#set text(font: "{{theme_font}}", size: {{theme_size}}pt)

= {{full_name}}
{{email}} | {{phone}} | {{location}}

{{#if summary}}
== Profile
{{summary}}
{{/if}}

{{#if experiences}}
== Projects & Experience
{{experiences}}
{{/if}}

{{#if skills}}
== Capabilities
{{skills}}
{{/if}}

{{#if education}}
== Education
{{education}}
{{/if}}
