import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";

// 토큰 → 시맨틱 → 기본 조판 → 부품 순으로 얹는다. 순서가 바뀌면 안 된다.
import "./styles/krds_tokens.css";
import "./styles/semantic.css";
import "./styles/base.css";
import "./styles/components.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
