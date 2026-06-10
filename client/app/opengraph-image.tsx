import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#131313",
        }}
      >
        <img
          src={`${baseUrl}/formalytx_light.svg`}
          alt="formalytx logo"
          width={120}
          height={77}
          style={{ marginBottom: 32 }}
        />

        <div
          style={{
            fontSize: 76,
            fontWeight: 700,
            color: "#ffffff",
            letterSpacing: "-2px",
            lineHeight: 1,
            marginBottom: 20,
          }}
        >
          Formalytx
        </div>

        <div
          style={{
            fontSize: 28,
            color: "#888888",
            marginBottom: 48,
          }}
        >
          Formula 1 data, decoded.
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 20px",
            border: "1px solid #2ADA8D",
            color: "#2ADA8D",
            fontSize: 13,
            letterSpacing: "0.18em",
          }}
        >
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#2ADA8D",
            }}
          />
          POWERED BY FASTF1
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
