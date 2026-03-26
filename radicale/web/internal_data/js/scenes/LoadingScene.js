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

import { get_element_by_id } from "../utils/misc.js";
import { Scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class LoadingScene {
    constructor() {
        this.html_scene = get_element_by_id("loadingscene");
    }
    show() {
        this.html_scene.classList.remove("hidden");
    }
    hide() {
        this.html_scene.classList.add("hidden");
    }
    release() { }
    is_transient() { return true; }
}