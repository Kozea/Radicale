/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

import { SERVER } from "../constants.js";

/**
 * @interface
 */
export class Scene {
    constructor() { }
    /**
     * Scene is on top of stack and visible.
     */
    show() { }
    /**
     * Scene is no longer visible.
     */
    hide() { }
    /**
     * Scene is removed from scene stack.
     */
    release() { }
    /**
     * Whether the scene should be excluded from browser history.
     * @returns boolean
     */
    is_transient() { return false; }

    /** @returns str */
    title_object() { return ""; }
}


/**
 * @type {Array<Scene>}
 */
let scene_stack = [];

/** @type {Array<Array<Scene>>} */
let history_array = [];
let current_history_index = -1;
let is_navigating_history = false;

function update_window_title() {
    let title_parts = ["Radicale Web Interface", SERVER];

    if (scene_stack.length > 0) {
        let title = scene_stack[scene_stack.length - 1].title_object();
        if (title) {
            title_parts.push(title);
        }
    }
    document.title = title_parts.join(" - ");
}

function record_history() {
    if (is_navigating_history) return;

    let current_scene = scene_stack.length > 0 ? scene_stack[scene_stack.length - 1] : null;
    if (current_scene && current_scene.is_transient && current_scene.is_transient()) {
        return;
    }

    // Compare with current history to avoid duplicates
    if (history_array.length > 0 && current_history_index >= 0) {
        let last_stack = history_array[current_history_index];
        if (last_stack && last_stack.length === scene_stack.length) {
            let is_identical = true;
            for (let i = 0; i < scene_stack.length; i++) {
                if (last_stack[i] !== scene_stack[i]) {
                    is_identical = false;
                    break;
                }
            }
            if (is_identical) return;
        }
    }

    history_array.splice(current_history_index + 1);
    history_array.push(scene_stack.slice());
    current_history_index++;

    // Check if this is the first history entry we are recording
    if (typeof window !== "undefined" && window.history) {
        if (current_history_index === 0) {
            history.replaceState({ history_index: current_history_index }, '');
        } else {
            history.pushState({ history_index: current_history_index }, '');
        }
    }
}

if (typeof window !== "undefined" && window.history) {
    if (!history.state || typeof history.state.history_index !== "number") {
        current_history_index = -1;
    } else {
        // If there's an existing state but we just loaded, we don't have the history_array memory.
        // We'll reset it. The user will be redirected to the root if they go back out of bounds.
        current_history_index = -1;
    }

    window.addEventListener("popstate", (event) => {
        if (!event.state || typeof event.state.history_index !== "number") return;
        let new_index = event.state.history_index;

        if (new_index >= 0 && new_index < history_array.length) {
            is_navigating_history = true;
            try {
                let new_stack = history_array[new_index];

                if (scene_stack.length > 0) {
                    scene_stack[scene_stack.length - 1].hide();
                }

                scene_stack = new_stack.slice();

                if (scene_stack.length > 0) {
                    scene_stack[scene_stack.length - 1].show();
                }

                current_history_index = new_index;
                update_window_title();
            } finally {
                is_navigating_history = false;
            }
        } else {
            // Out of bounds (e.g., from a previous session after a reload)
            window.location.reload();
        }
    });
}

/**
 * Push scene onto stack.
 * @param {Scene} scene
 */
export function push_scene(scene) {
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].hide();
    }
    scene_stack.push(scene);
    scene.show();
    record_history();
    update_window_title();
}

/**
 * Pop the current scene and release it.
 */
function pop_and_release() {
    if (scene_stack.length === 0) {
        return;
    }
    let scene = scene_stack.pop();
    if (scene) {
        scene.release();
    }
    update_window_title();
}

/**
 * Replace the current scene with a new one.
 * @param {Scene} scene
 */
export function replace_scene(scene) {
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].hide();
        pop_and_release();
    }
    scene_stack.push(scene);
    scene.show();
    record_history();
    update_window_title();
}

/**
 * Remove the current scene from the stack.
 */
export function pop_scene() {
    if (scene_stack.length === 0) {
        return;
    }
    scene_stack[scene_stack.length - 1].hide();
    pop_and_release();
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].show();
    }
    record_history();
    update_window_title();
}

/**
 * Pop the current scene and the one below it.
 * Useful for returning to the parent of the caller.
 */
export function pop_to_parent() {
    if (scene_stack.length === 0) {
        return;
    }
    scene_stack[scene_stack.length - 1].hide();
    pop_and_release();
    if (scene_stack.length >= 1) {
        pop_and_release();
    }
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].show();
    }
    record_history();
    update_window_title();
}

/**
 * Pop all scenes until only the root scene remains.
 * If the stack is empty, nothing happens.
 */
export function pop_to_root() {
    if (scene_stack.length === 0) {
        return;
    }
    // Pop all scenes until only the first one remains
    while (scene_stack.length > 1) {
        scene_stack[scene_stack.length - 1].hide();
        pop_and_release();
    }
    // The root scene is now at the top (index 0) and should be shown
    if (scene_stack.length === 1) {
        scene_stack[0].show(); // Ensure the root scene is visible
    }
    record_history();
    update_window_title();
}

/**
 * Check if the given scene is the current top scene.
 * @param {Scene} scene
 * @returns {boolean}
 */
export function is_current_scene(scene) {
    return scene_stack.length > 0 && scene_stack[scene_stack.length - 1] === scene;
}