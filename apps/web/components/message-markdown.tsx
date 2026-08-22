import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

function isExternalLink(href: string | undefined) {
  return Boolean(href && /^(?:https?:)?\/\//i.test(href));
}

export function MessageMarkdown({ content }: { content: string }) {
  return (
    <div className="message-markdown">
      <Markdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={["img"]}
        components={{
          h1: ({ children }) => <h3>{children}</h3>,
          h2: ({ children }) => <h3>{children}</h3>,
          a: ({ children, href, title }) => {
            const external = isExternalLink(href);
            return (
              <a
                href={href}
                title={title}
                target={external ? "_blank" : undefined}
                rel={external ? "noreferrer" : undefined}
              >
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}

export function MessageContent({
  authorType,
  content,
}: {
  authorType: string;
  content: string;
}) {
  if (authorType === "public_assistant" || authorType === "studio_assistant") {
    return <MessageMarkdown content={content} />;
  }
  return <p>{content}</p>;
}
