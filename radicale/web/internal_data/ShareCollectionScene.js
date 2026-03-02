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

import {
  add_share_by_token,
  delete_share_by_token,
  reload_sharing_list,
  server_features,
} from "./api.js";
import { pop_scene, scene_stack } from "./scene_manager.js";

/**
 * @constructor
 * @implements {Scene}
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection The collection on which to edit sharing setting. Must exist.
 */
export function CreateShareCollectionScene(user, password, collection) {
  /** @type {?number} */ let scene_index = null;

  let html_scene = document.getElementById("sharecollectionscene");

  let cancel_btn = html_scene.querySelector("[data-name=cancel]");
  let share_by_token_btn_ro = html_scene.querySelector(
    "[data-name=sharebytoken_ro]",
  );
  let share_by_token_btn_rw = html_scene.querySelector(
    "[data-name=sharebytoken_rw]",
  );

  let title = html_scene.querySelector("[data-name=title]");

  function oncancel() {
    try {
      pop_scene(scene_index - 1);
    } catch (err) {
      console.error(err);
    }
    return false;
  }

  function onsharebytoken_rw() {
    add_share_by_token(user, password, collection, "rw", function () {
      update_share_list(user, password, collection);
    });
  }

  function onsharebytoken_ro() {
    add_share_by_token(user, password, collection, "r", function () {
      update_share_list(user, password, collection);
    });
  }

  this.show = function () {
    this.release();
    scene_index = scene_stack.length - 1;
    html_scene.classList.remove("hidden");
    cancel_btn.onclick = oncancel;
    if (server_features["sharing"]["FeatureEnabledCollectionByToken"]) {
      share_by_token_btn_ro.onclick = onsharebytoken_ro;
      share_by_token_btn_rw.onclick = onsharebytoken_rw;
    } else {
      share_by_token_btn_ro.parentElement.removeChild(share_by_token_btn_ro);
      share_by_token_btn_rw.parentElement.removeChild(share_by_token_btn_rw);
    }
    title.textContent = collection.displayname || collection.href;
    update_share_list(user, password, collection);
  };
  this.hide = function () {
    html_scene.classList.add("hidden");
    cancel_btn.onclick = null;
  };
  this.release = function () {
    scene_index = null;
  };
}

function update_share_list(user, password, collection) {
  let share_rows = document.querySelectorAll(
    "[data-name=sharetokenrowtemplate]",
  );
  share_rows.forEach(function (row) {
    if (!row.classList.contains("hidden")) {
      row.parentNode.removeChild(row);
    }
  });

  reload_sharing_list(user, password, collection, function (response) {
    add_share_rows(user, password, collection, response["Content"] || []);
  });
}

function add_share_rows(user, password, collection, shares) {
  let template = document.querySelector("[data-name=sharetokenrowtemplate]");
  shares.forEach(function (share) {
    let pathortoken = share["PathOrToken"] || "";
    let pathmapped = share["PathMapped"] || "";
    if (
      collection.href.includes(pathmapped) ||
      collection.href.includes(pathortoken)
    ) {
      let node = template.cloneNode(true);
      node.classList.remove("hidden");
      node.querySelector("[data-name=pathortoken]").value = pathortoken;
      let permissions = (share["Permissions"] || "").toLowerCase();
      if (permissions === "rw") {
        node
          .querySelector("[data-name=ro]")
          .parentNode.removeChild(node.querySelector("[data-name=ro]"));
      } else if (permissions === "r") {
        node
          .querySelector("[data-name=rw]")
          .parentNode.removeChild(node.querySelector("[data-name=rw]"));
      } else {
        console.warn("Unknown permissions", permissions);
      }
      node.querySelector("[data-name=delete]").onclick = function () {
        delete_share_by_token(
          user,
          password,
          share["PathOrToken"],
          function () {
            update_share_list(user, password, collection);
          },
        );
      };

      template.parentNode.insertBefore(node, template);
    }
  });
}

export function maybe_enable_sharing_options() {
  if (!server_features["sharing"]) return;
  let map_is_enabled =
    server_features["sharing"]["FeatureEnabledCollectionByMap"] || false;
  let token_is_enabled =
    server_features["sharing"]["FeatureEnabledCollectionByToken"] || false;
  if (map_is_enabled || token_is_enabled) {
    let share_options = document.querySelectorAll("[data-name=shareoption]");
    for (let i = 0; i < share_options.length; i++) {
      let share_option = share_options[i];
      share_option.classList.remove("hidden");
    }
  }
}
