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
}


/**
 * @type {Array<Scene>}
 */
let scene_stack = [];

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
}

/**
 * Replace the current scene with a new one.
 * @param {Scene} scene
 */
export function replace_scene(scene) {
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].hide();
        scene_stack.pop().release();
    }
    scene_stack.push(scene);
    scene.show();
}

/**
 * Remove the current scene from the stack.
 */
export function pop_scene() {
    if (scene_stack.length === 0) {
        return;
    }
    scene_stack[scene_stack.length - 1].hide();
    scene_stack.pop().release();
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].show();
    }
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
    scene_stack.pop().release();
    if (scene_stack.length >= 1) {
        scene_stack.pop().release();
    }
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].show();
    }
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
        scene_stack.pop().release();
    }
    // The root scene is now at the top (index 0) and should be shown
    if (scene_stack.length === 1) {
        scene_stack[0].show(); // Ensure the root scene is visible
    }
}

/**
 * Check if the given scene is the current top scene.
 * @param {Scene} scene
 * @returns {boolean}
 */
export function is_current_scene(scene) {
    return scene_stack.length > 0 && scene_stack[scene_stack.length - 1] === scene;
}