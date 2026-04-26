/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2026-2026 Max Berger <max@berger.name>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * Utilities for resource URL boxes
 */

import { completeHref } from "./misc.js";

/**
 * Handles the display of URLs in input fields.
 */
export class UrlTextHandler {
    /** @type {?HTMLCanvasElement} */
    static _canvas = null;

    /**
     * @param {HTMLInputElement} element The input element to handle.
     * @param {HTMLButtonElement} copyButton The button element for copying.
     */
    constructor(element, copyButton) {
        this._element = element;
        this._copyButton = copyButton;
        this._userIndex = -1;

        this._element.addEventListener("focusin", () => {
            this._element.setSelectionRange(0, 99999);
            this._updateScroll();
        });
        this._element.addEventListener("focusout", () => {
            this._updateScroll();
        });

        if (this._copyButton) {
            this._copyButton.onclick = () => this._oncopy();
        }
    }

    _updateScroll() {
        setTimeout(() => {
            this._updateScroll_now();
        }, 0);
    }

    /**
     * Update the scroll position of the input field.
     */
    _updateScroll_now() {
        if (this._userIndex === -1) {
            this._element.scrollLeft = this._element.scrollWidth;
            return;
        }

        let scrollPos = this._element.scrollWidth;
        const value = this._element.value;
        const style = window.getComputedStyle(this._element);
        if (!UrlTextHandler._canvas) {
            UrlTextHandler._canvas = document.createElement("canvas");
        }
        const context = UrlTextHandler._canvas.getContext("2d");
        if (context) {
            context.font = style.font;
            const prefix = value.substring(0, this._userIndex);
            scrollPos = context.measureText(prefix).width;
        }

        this._element.scrollLeft = scrollPos;
    }

    /**
     * Copy the current value of the input to the clipboard.
     */
    _oncopy() {
        if (!this._element.value) return;

        navigator.clipboard.writeText(this._element.value).then(() => {
            if (this._copyButton) {
                this._copyButton.classList.add("copied");
                this._copyButton.title = "Copied!";
                setTimeout(() => {
                    this._copyButton.classList.remove("copied");
                    this._copyButton.title = "copy";
                }, 1500);
            }
        }).catch(err => {
            console.error("Could not copy text: ", err);
        });
    }

    /**
     * Set the value of the input field to the given href.
     * If the href is relative, it will be prefixed with the server URL.
     * @param {string} href The href to set.
     */
    setHref(href) {
        this._element.value = completeHref(href);

        this._update_username_index();
        this._updateScroll();
    }

    /**
     * Update the username index.
     */
    _update_username_index() {
        const value = this._element.value;
        this._userIndex = -1;
        try {
            const url = new URL(value);
            const path = url.pathname;
            const parts = path.split("/").filter(p => p !== "");
            if (parts.length >= 2) {
                const user = parts[parts.length - 2];
                const search = "/" + user + "/";
                const pathIndex = path.lastIndexOf(search);
                if (pathIndex !== -1) {
                    const fullIndex = value.lastIndexOf(path);
                    if (fullIndex !== -1) {
                        this._userIndex = fullIndex + pathIndex;
                    }
                }
            }
        } catch (e) {
            this._userIndex = -1;
        }
    }
}
