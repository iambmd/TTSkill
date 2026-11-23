"use client";

import { useEffect } from "react";

export function HomeMotion() {
  useEffect(() => {
    const observer = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) {
          target.classList.add("home-entered");
          observer?.unobserve(target);
        }
      });
    }, { threshold: 0.12 }) : undefined;
    document.querySelectorAll("[data-home-enter]").forEach((element) => observer?.observe(element));
    return () => observer?.disconnect();
  }, []);

  return null;
}
