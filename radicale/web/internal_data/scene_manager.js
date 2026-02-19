/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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
export function Scene() {}
/**
 * Scene is on top of stack and visible.
 */
Scene.prototype.show = function() {};
/**
 * Scene is no longer visible.
 */
Scene.prototype.hide = function() {};
/**
 * Scene is removed from scene stack.
 */
Scene.prototype.release = function() {};


/**
 * @type {Array<Scene>}
 */
export let scene_stack = [];

/**
 * Push scene onto stack.
 * @param {Scene} scene
 * @param {boolean} replace Replace the scene on top of the stack.
 */
export function push_scene(scene, replace) {
    if (scene_stack.length >= 1) {
        scene_stack[scene_stack.length - 1].hide();
        if (replace) {
            scene_stack.pop().release();
        }
    }
    scene_stack.push(scene);
    scene.show();
}

/**
 * Remove scenes from stack.
 * @param {number} index New top of stack
 */
export function pop_scene(index) {
    if (scene_stack.length - 1 <= index) {
        return;
    }
    scene_stack[scene_stack.length - 1].hide();
    while (scene_stack.length - 1 > index) {
        let old_length = scene_stack.length;
        scene_stack.pop().release();
        if (old_length - 1 === index + 1) {
            break;
        }
    }
    if (scene_stack.length >= 1) {
        let scene = scene_stack[scene_stack.length - 1];
        scene.show();
    } else {
        throw "Scene stack is empty";
    }
}