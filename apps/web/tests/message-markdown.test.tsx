import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MessageContent, MessageMarkdown } from "@/components/message-markdown";

afterEach(cleanup);

describe("message Markdown rendering", () => {
  it("renders common Markdown and GitHub-flavored formatting", () => {
    const { container } = render(
      <MessageMarkdown
        content={[
          "## Passi successivi",
          "",
          "- **Verifica** i documenti",
          "- Chiedi una *valutazione*",
          "",
          "~~Bozza~~ Definitivo",
          "",
          "| Zona | Stato |",
          "| --- | --- |",
          "| Roma Nord | Pronto |",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("heading", { level: 3, name: "Passi successivi" })).toBeInTheDocument();
    expect(screen.getByText("Verifica").tagName).toBe("STRONG");
    expect(screen.getByText("valutazione").tagName).toBe("EM");
    expect(screen.getByText("Bozza").tagName).toBe("DEL");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByRole("table")).toHaveTextContent("Roma Nord");
  });

  it("keeps links safe and does not load Markdown images or raw HTML", () => {
    const { container } = render(
      <MessageMarkdown
        content={[
          "[Guida](https://example.com/guida)",
          "[Script](javascript:alert('no'))",
          "",
          "![Pixel](https://tracker.example/pixel.png)",
          "",
          "<script>alert('no')</script>",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("link", { name: "Guida" })).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: "Guida" })).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("Script").closest("a")).toHaveAttribute("href", "");
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector("script")).not.toBeInTheDocument();
    expect(container).not.toHaveTextContent("alert('no')");
  });

  it("keeps visitor and professional records literal while rendering assistant Markdown", () => {
    const { rerender } = render(
      <MessageContent authorType="visitor" content="[contratto](https://example.com/falso)" />,
    );

    expect(screen.queryByRole("link", { name: "contratto" })).not.toBeInTheDocument();
    expect(screen.getByText("[contratto](https://example.com/falso)")).toBeInTheDocument();

    rerender(
      <MessageContent authorType="public_assistant" content="[contratto](https://example.com/vero)" />,
    );
    expect(screen.getByRole("link", { name: "contratto" })).toHaveAttribute(
      "href",
      "https://example.com/vero",
    );
  });
});
