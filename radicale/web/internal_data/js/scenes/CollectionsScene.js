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

import { delete_collection } from "../api/api.js";
import { get_auth_header } from "../api/common.js";
import { delete_share_by_map, update_incoming_share } from "../api/sharing.js";
import { ROOT_PATH, SERVER } from "../constants.js";
import { Collection, CollectionType, Permission } from "../models/collection.js";
import { extract_title } from "../utils/collection_utils.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { bytesToHumanReadable, decode_and_strip_trailing_slashes, get_element, get_element_by_id, strip_leading_slashes, strip_trailing_slashes } from "../utils/misc.js";
import { displayPermissions } from "../utils/permissions.js";
import { UrlTextHandler } from "../utils/url_text.js";
import { CreateEditCollectionScene } from "./CreateEditCollectionScene.js";
import { DeleteConfirmationScene } from "./DeleteConfirmationScene.js";
import { Scene, push_scene } from "./scene_manager.js";
import { ShareCollectionScene } from "./ShareCollectionScene.js";
import { UploadCollectionScene } from "./UploadCollectionScene.js";

/**
 * Finds a matching map share for a given collection href and current user.
 * @param {string} collectionHref
 * @param {import("../api/sharing.js").Share[]} shares
 * @returns {import("../api/sharing.js").Share | undefined}
 */
function find_matching_map_share(collectionHref, shares) {
    let collHref = decode_and_strip_trailing_slashes(collectionHref);
    return (shares || []).find(s => {
        if (s.ShareType !== "map") return false;
        let shareMapped = decode_and_strip_trailing_slashes(s.PathMapped);
        if (collHref === shareMapped || collHref.endsWith("/" + strip_leading_slashes(shareMapped))) {
            return false;
        }
        let shareTarget = decode_and_strip_trailing_slashes(s.PathOrToken);
        return collHref === shareTarget || collHref.endsWith(shareTarget);
    });
}

/**
 * Checks whether a share is an incoming map share for the given user.
 * @param {import("../api/sharing.js").Share} share
 * @param {string} currentUser
 * @returns {boolean}
 */
function is_incoming_map_share(share, currentUser) {
    if (share.ShareType !== "map" || share.Owner === currentUser) {
        return false;
    }
    let cleanUser = decodeURIComponent(currentUser || "");
    let prefix = "/" + cleanUser + "/";
    let target = decodeURIComponent(share.PathOrToken || "").replace("{user}", cleanUser);
    if (!target.startsWith("/")) {
        target = "/" + target;
    }
    return target.startsWith(prefix);
}

/**
 * Creates a synthetic Collection object from an incoming Share.
 * @param {import("../api/sharing.js").Share} share
 * @param {string} currentUser
 * @returns {Collection}
 */
function create_synthetic_collection_from_share(share, currentUser) {
    let cleanUser = decodeURIComponent(currentUser || "");
    let href = decodeURIComponent(share.PathOrToken || "").replace("{user}", cleanUser);
    if (!href.startsWith("/")) {
        href = "/" + href;
    }
    if (!href.endsWith("/")) {
        href += "/";
    }

    let is_addressbook = strip_trailing_slashes(share.PathMapped).endsWith(".vcf") && share.Conversion !== "bday";
    let type = is_addressbook ? CollectionType.ADDRESSBOOK : CollectionType.CALENDAR;
    let pathName = strip_trailing_slashes(href).split("/").pop() || "";
    let displayname = (share.Properties && share.Properties["D:displayname"]) || pathName;
    let description = (share.Properties && (share.Properties["C:calendar-description"] || share.Properties["CR:addressbook-description"])) || "";
    let color = (share.Properties && (share.Properties["ICAL:calendar-color"] || share.Properties["INF:addressbook-color"])) || "";

    /** @type {Array<string>} */
    let permissions = [];
    if (/w/i.test(share.Permissions || "")) {
        permissions.push(Permission.WRITE, Permission.WRITE_CONTENT);
    }
    if (/P/i.test(share.Permissions || "")) {
        permissions.push(Permission.WRITE_PROPERTIES);
    }

    return new Collection(
        href,
        type,
        displayname,
        description,
        color,
        0,
        0,
        "",
        permissions,
        ""
    );
}

/**
 * Finds incoming map shares that do not yet have a matching collection in the collections list.
 * @param {Collection[]} collections
 * @param {import("../api/sharing.js").Share[]} shares
 * @param {string} currentUser
 * @returns {Collection[]}
 */
function get_missing_incoming_collections(collections, shares, currentUser) {
    /** @type {Array<Collection>} */
    let missing = [];
    (shares || []).forEach((share) => {
        if (!is_incoming_map_share(share, currentUser)) {
            return;
        }
        let already_present = collections.some(c => Boolean(find_matching_map_share(c.href, [share])));
        if (!already_present) {
            missing.push(create_synthetic_collection_from_share(share, currentUser));
        }
    });
    return missing;
}

/**
 * Updates CSS classes, toggle button states, and action button visibility for an incoming share card.
 * @param {HTMLElement} node
 * @param {import("../api/sharing.js").Share} share
 * @param {HTMLButtonElement} enabled_btn
 * @param {HTMLButtonElement} shown_btn
 * @param {HTMLElement} edit_btn
 * @param {HTMLAnchorElement} download_btn
 * @param {Collection} collection
 */
function update_share_card_state(node, share, enabled_btn, shown_btn, edit_btn, download_btn, collection) {
    let isGroupOrRealm = (share.Permissions || "").includes("U");
    let enabled = share.EnabledByUser !== null ? share.EnabledByUser : true;
    let shown = share.HiddenByUser !== null ? !share.HiddenByUser : true;

    // Card styling
    if (!enabled) {
        node.classList.add("share-disabled");
        node.classList.remove("share-hidden");
    } else if (!shown) {
        node.classList.remove("share-disabled");
        node.classList.add("share-hidden");
    } else {
        node.classList.remove("share-disabled");
        node.classList.remove("share-hidden");
    }

    // Enabled button
    /** @type {HTMLImageElement | null} */
    let enabled_icon = enabled_btn.querySelector("img");
    if (enabled) {
        enabled_btn.classList.add("active", "green");
        enabled_btn.classList.remove("inactive");
        enabled_btn.title = "Enabled";
        if (enabled_icon) {
            enabled_icon.src = "css/icons/check-circle.svg";
            enabled_icon.alt = "Enabled";
        }
    } else {
        enabled_btn.classList.add("inactive");
        enabled_btn.classList.remove("active", "green");
        enabled_btn.title = "Disabled";
        if (enabled_icon) {
            enabled_icon.src = "css/icons/minus-circle.svg";
            enabled_icon.alt = "Disabled";
        }
    }

    // Shown button
    if (shown) {
        shown_btn.classList.add("active", "green");
        shown_btn.classList.remove("inactive");
        shown_btn.title = "Shown";
    } else {
        shown_btn.classList.add("inactive");
        shown_btn.classList.remove("active", "green");
        shown_btn.title = "Hidden";
    }

    // Group / realm shares
    if (isGroupOrRealm) {
        enabled_btn.disabled = true;
        shown_btn.disabled = true;
        enabled_btn.title = "Group and domain shares cannot be disabled";
        shown_btn.title = "Group and domain shares cannot be hidden";
    } else {
        enabled_btn.disabled = false;
        shown_btn.disabled = !enabled;
    }

    // Action buttons (edit and download)
    let has_write_permission = /w/i.test(share.Permissions || "");
    let has_write_properties = /P/i.test(share.Permissions || "") || collection.has_permission(Permission.WRITE_PROPERTIES);
    if (enabled && (has_write_permission || has_write_properties)) {
        edit_btn.classList.remove("hidden");
        if (edit_btn.parentElement) {
            edit_btn.parentElement.classList.remove("hidden");
        }
    } else {
        edit_btn.classList.add("hidden");
        if (edit_btn.parentElement) {
            edit_btn.parentElement.classList.add("hidden");
        }
    }

    if (collection.type == CollectionType.WEBCAL || !enabled) {
        if (download_btn.parentElement) {
            download_btn.parentElement.classList.add("hidden");
        }
    } else {
        if (download_btn.parentElement) {
            download_btn.parentElement.classList.remove("hidden");
        }
    }
}

/**
 * @implements {Scene}
 */
export class CollectionsScene {
    /**
     * @param {string} user
     * @param {?string} password
     * @param {Collection} principal_collection The princial collection
     * @param {(error: string | null) => void} onerror Called when an error occurs, before the
     *                                   scene is popped.
     */
    constructor(user, password, principal_collection, onerror) {
        this._user = user;
        this._password = password;
        this._principal_collection = principal_collection;
        this._onerror = onerror;

        this._html_scene = get_element_by_id("collectionsscene");
        this._template = get_element(this._html_scene, "[data-name=collectiontemplate]");
        this._new_btn = get_element(this._html_scene, "[data-name=new]");
        this._upload_btn = get_element(this._html_scene, "[data-name=upload]");
        /** @type {HTMLAnchorElement} */
        this._mobileconfig_btn = /** @type {HTMLAnchorElement} */ (get_element(this._html_scene, "[data-name=mobileconfig]"));
        this._error_div = get_element(this._html_scene, "[data-name=collectionsscene_error]");

        /** @type {Array<HTMLElement>} */ this._nodes = [];
        this._errorHandler = new ErrorHandler(this._error_div);
    }

    _onnew() {
        try {
            let create_collection_scene = new CreateEditCollectionScene(this._user, this._password, this._principal_collection);
            push_scene(create_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    _onupload() {
        try {
            let upload_scene = new UploadCollectionScene(this._user, this._password, this._principal_collection);
            push_scene(upload_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {Collection} collection
     */
    _onedit(collection) {
        try {
            let edit_collection_scene = new CreateEditCollectionScene(this._user, this._password, collection);
            push_scene(edit_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {Collection} collection
     */
    _onshare(collection) {
        try {
            let share_collection_scene = new ShareCollectionScene(this._user, this._password, collection);
            push_scene(share_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {Collection} collection
     * @param {import("../api/sharing.js").Share | null} [share]
     */
    _ondelete(collection, share = null) {
        try {
            let delete_action = share ? delete_share_by_map : delete_collection;
            let title = share ? "Delete Shared Item" : "Delete Collection";
            let item = share || collection;
            let delete_collection_scene = new DeleteConfirmationScene(
                this._user, this._password, title, item, extract_title(collection),
                delete_action, true
            );
            push_scene(delete_collection_scene);
        } catch (err) {
            console.error(err);
        }
        return false;
    }

    /**
     * @param {import("../api/sharing.js").Share} share
     * @param {HTMLElement} node
     * @param {HTMLButtonElement} enabled_btn
     * @param {HTMLButtonElement} shown_btn
     * @param {HTMLElement} edit_btn
     * @param {HTMLAnchorElement} download_btn
     * @param {Collection} collection
     */
    _toggle_share_enabled(share, node, enabled_btn, shown_btn, edit_btn, download_btn, collection) {
        if (enabled_btn.disabled) return;
        enabled_btn.disabled = true;
        shown_btn.disabled = true;

        let old_enabled = share.EnabledByUser !== null ? share.EnabledByUser : true;
        let old_hidden = share.HiddenByUser !== null ? share.HiddenByUser : false;

        share.EnabledByUser = !old_enabled;
        this._errorHandler.clearError();
        update_share_card_state(node, share, enabled_btn, shown_btn, edit_btn, download_btn, collection);
        enabled_btn.disabled = true;
        shown_btn.disabled = true;

        update_incoming_share(this._user, this._password, share, (error) => {
            if (error) {
                this._errorHandler.setError(error);
                share.EnabledByUser = old_enabled;
                share.HiddenByUser = old_hidden;
                update_share_card_state(node, share, enabled_btn, shown_btn, edit_btn, download_btn, collection);
            } else {
                collectionsCache.invalidate();
                enabled_btn.disabled = false;
                shown_btn.disabled = !share.EnabledByUser;
            }
        });
    }

    /**
     * @param {import("../api/sharing.js").Share} share
     * @param {HTMLElement} node
     * @param {HTMLButtonElement} enabled_btn
     * @param {HTMLButtonElement} shown_btn
     * @param {HTMLElement} edit_btn
     * @param {HTMLAnchorElement} download_btn
     * @param {Collection} collection
     */
    _toggle_share_shown(share, node, enabled_btn, shown_btn, edit_btn, download_btn, collection) {
        if (shown_btn.disabled) return;
        enabled_btn.disabled = true;
        shown_btn.disabled = true;

        let old_hidden = share.HiddenByUser !== null ? share.HiddenByUser : false;

        share.HiddenByUser = !old_hidden;
        this._errorHandler.clearError();
        update_share_card_state(node, share, enabled_btn, shown_btn, edit_btn, download_btn, collection);
        enabled_btn.disabled = true;
        shown_btn.disabled = true;

        update_incoming_share(this._user, this._password, share, (error) => {
            if (error) {
                this._errorHandler.setError(error);
                share.HiddenByUser = old_hidden;
                update_share_card_state(node, share, enabled_btn, shown_btn, edit_btn, download_btn, collection);
            } else {
                collectionsCache.invalidate();
                enabled_btn.disabled = false;
                shown_btn.disabled = false;
            }
        });
    }

    /**
     * Sorts collections into 4 tiers, alphabetically by title within each tier:
     * - Tier 1: Own collections (not an incoming share, or owned by current user)
     * - Tier 2: Active incoming shares (enabled: true, shown: true)
     * - Tier 3: Hidden incoming shares (enabled: true, shown: false)
     * - Tier 4: Disabled incoming shares (enabled: false)
     * @param {Collection[]} collections
     * @param {import("../api/sharing.js").Share[]} shares
     */
    _sort_collections(collections, shares) {
        /**
         * @param {Collection} collection
         * @returns {number}
         */
        const get_tier = (collection) => {
            const share = find_matching_map_share(collection.href, shares);
            // Tier 1: Own collections (not an incoming share, or owned by current user)
            if (!share || share.Owner === this._user) {
                return 1;
            }
            const enabled = share.EnabledByUser !== null ? share.EnabledByUser : true;
            const shown = share.HiddenByUser !== null ? !share.HiddenByUser : true;
            // Tier 2: Active incoming shares (both enabled and shown)
            if (enabled && shown) {
                return 2;
            }
            // Tier 3: Hidden incoming shares (enabled, but hidden)
            if (enabled && !shown) {
                return 3;
            }
            // Tier 4: Disabled incoming shares (disabled; hidden status irrelevant)
            return 4;
        };

        collections.sort((a, b) => {
            const tierA = get_tier(a);
            const tierB = get_tier(b);

            if (tierA !== tierB) {
                return tierA - tierB;
            }

            return extract_title(a).localeCompare(extract_title(b));
        });
    }

    /**
     * Clears all collection nodes from the DOM and resets the nodes array.
     */
    _clear_collections_display() {
        this._nodes.forEach(function (node) {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        });
        this._nodes = [];
    }

    /**
     * Sets up the scene layout by adjusting margins based on the navbar height.
     */
    _setup_layout() {
        /** @type {HTMLElement} */ let navBar = get_element(document, "#logoutview");
        let heightOfNavBar = navBar.offsetHeight + "px";
        this._html_scene.style.marginTop = heightOfNavBar;
        this._html_scene.style.height = "calc(100vh - " + heightOfNavBar + ")";
    }

    /**
     * Download a file from the server, authenticated with user/password if available.
     * Extracts filename from Content-Disposition header if present, falling back to fallback_filename.
     *
     * @param {string} url
     * @param {string} [fallback_filename]
     */
    _download_file(url, fallback_filename) {
        let auth = get_auth_header(this._user, this._password);
        let headers = auth ? {
            'Authorization': auth
        } : undefined;
        fetch(url, { headers: headers }).then((response) => {
            if (response.ok) {
                let filename = fallback_filename;
                let disposition = response.headers.get("Content-Disposition");
                if (disposition) {
                    let match = disposition.match(/filename\*?=(?:UTF-8'')?("?[^";\n]*"?)/i);
                    if (match && match[1]) {
                        filename = decodeURIComponent(match[1].replace(/^["']|["']$/g, ''));
                    }
                }
                return response.blob().then((blob) => ({ blob, filename }));
            }
            throw new Error("Download failed: " + response.statusText);
        }).then(({ blob, filename }) => {
            let blob_url = window.URL.createObjectURL(blob);
            let a = document.createElement("a");
            a.href = blob_url;
            if (filename) {
                a.download = filename;
            }
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(blob_url);
        })["catch"]((error) => {
            this._errorHandler.setError(error.message);
        });
    }

    /**
     * @param {Collection} collection
     * @param {import("../api/sharing.js").Share[]} shares
     */
    _render_collection(collection, shares) {
        /** @type {HTMLElement} */ let node = /** @type {HTMLElement} */(this._template.cloneNode(true));
        node.classList.remove("hidden");
        /** @type {HTMLElement} */ let title_form = get_element(node, "[data-name=title]");
        /** @type {HTMLElement} */ let description_form = get_element(node, "[data-name=description]");
        /** @type {HTMLElement} */ let contentcount_form = get_element(node, "[data-name=contentcount]");
        /** @type {HTMLInputElement} */ let url_form = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=url]"));
        /** @type {HTMLElement} */ let color_form = get_element(node, "[data-name=color]");
        /** @type {HTMLElement} */ let delete_btn = get_element(node, "[data-name=delete]");
        /** @type {HTMLElement} */ let edit_btn = get_element(node, "[data-name=edit]");
        /** @type {HTMLElement} */ let share_btn = get_element(node, "[data-name=share]");
        /** @type {HTMLAnchorElement} */ let download_btn = /** @type {HTMLAnchorElement} */ (get_element(node, "[data-name=download]"));
        /** @type {HTMLButtonElement} */ let copy_btn = /** @type {HTMLButtonElement} */ (get_element(node, "[data-name=copy-url]"));
        /** @type {HTMLElement} */ let freebusy_wrapper = get_element(node, "[data-name=freebusy-url-wrapper]");
        /** @type {HTMLInputElement} */ let freebusy_url_form = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=freebusy-url]"));
        /** @type {HTMLButtonElement} */ let freebusy_copy_btn = /** @type {HTMLButtonElement} */ (get_element(node, "[data-name=copy-freebusy-url]"));
        /** @type {HTMLElement} */ let permissions_container = get_element(node, "[data-name=permissions]");
        /** @type {HTMLElement} */ let share_option = get_element(node, "[data-name=shareoption]");
        /** @type {HTMLElement} */ let share_control_enabled_li = get_element(node, "[data-name=share-control-enabled]");
        /** @type {HTMLElement} */ let share_control_shown_li = get_element(node, "[data-name=share-control-shown]");
        /** @type {HTMLButtonElement} */ let enabled_btn = /** @type {HTMLButtonElement} */ (get_element(node, "button[data-name=enabled]"));
        /** @type {HTMLButtonElement} */ let shown_btn = /** @type {HTMLButtonElement} */ (get_element(node, "button[data-name=shown]"));
        if (collection.color) {
            color_form.style.background = collection.color;
        }
        let possible_types = [CollectionType.ADDRESSBOOK, CollectionType.WEBCAL];
        [CollectionType.CALENDAR, ""].forEach(function (e) {
            [CollectionType.union(e, CollectionType.JOURNAL), e].forEach(function (e) {
                [CollectionType.union(e, CollectionType.TASKS), e].forEach(function (e) {
                    if (e) {
                        possible_types.push(e);
                    }
                });
            });
        });
        possible_types.forEach(function (e) {
            if (e !== collection.type) {
                get_element(node, "[data-name=" + e + "]").classList.add("hidden");
            }
        });

        if (permissions_container) {
            displayPermissions(collection, permissions_container);
        }

        let can_share = collection.has_permission(Permission.SHARE_MAP) || collection.has_permission(Permission.SHARE_TOKEN);
        if (share_option) {
            if (can_share) {
                share_option.classList.remove("hidden");
            } else {
                share_option.classList.add("hidden");
            }
        }

        title_form.textContent = collection.displayname || decodeURIComponent(collection.href);
        if (title_form.textContent.length > 30) {
            title_form.classList.add("smalltext");
        }
        description_form.textContent = collection.description;
        if (description_form.textContent.length > 150) {
            description_form.classList.add("smalltext");
        }
        if (collection.type != CollectionType.WEBCAL) {
            let contentcount_form_txt = (collection.contentcount > 0 ? Number(collection.contentcount).toLocaleString() : "No") + " item" + (collection.contentcount == 1 ? "" : "s") + " in collection";
            if (collection.contentcount > 0) {
                contentcount_form_txt += " (" + bytesToHumanReadable(collection.size) + ")";
            }
            contentcount_form.textContent = contentcount_form_txt;
        }

        let href = window.location.origin + collection.href;
        new UrlTextHandler(url_form, copy_btn).setHref(href);
        let share = find_matching_map_share(collection.href, shares);
        let is_transform = Boolean(share &&
            (share.Conversion || "").toLowerCase() !== "none" &&
            (share.Conversion || "") !== "");
        if (CollectionType.is_subset(CollectionType.CALENDAR, collection.type) &&
                !is_transform) {
            freebusy_wrapper.classList.remove("hidden");
            new UrlTextHandler(freebusy_url_form, freebusy_copy_btn).setHref(
                href + "?view=freebusy");
        }
        download_btn.href = href;
        download_btn.onclick = (event) => {
            event.preventDefault();
            let fallback = strip_trailing_slashes(collection.displayname || collection.href) + (collection.type === CollectionType.ADDRESSBOOK ? ".vcf" : ".ics");
            this._download_file(href, fallback);
        };
        if (collection.type == CollectionType.WEBCAL) {
            if (download_btn.parentElement) {
                download_btn.parentElement.classList.add("hidden");
            }
        }

        let share_info = get_element(node, "[data-name=shared-by]");
        let transformed_from = get_element(node, "[data-name=transformed-from]");
        let is_incoming_share = false;
        let is_self_owned_share = Boolean(share && share.Owner === this._user);
        if (share) {
            if (share.Owner !== this._user) {
                is_incoming_share = true;
                share_info.classList.remove("hidden");
                get_element(node, "[data-name=shared-by-owner]").textContent = share.Owner;

                share_control_enabled_li.classList.remove("hidden");
                share_control_shown_li.classList.remove("hidden");

                update_share_card_state(node, share, enabled_btn, shown_btn, edit_btn, download_btn, collection);

                enabled_btn.onclick = () => {
                    this._toggle_share_enabled(share, node, enabled_btn, shown_btn, edit_btn, download_btn, collection);
                };
                shown_btn.onclick = () => {
                    this._toggle_share_shown(share, node, enabled_btn, shown_btn, edit_btn, download_btn, collection);
                };
            } else {
                transformed_from.classList.remove("hidden");
                share_control_enabled_li.classList.add("hidden");
                share_control_shown_li.classList.add("hidden");
            }
            let share_option = get_element(node, "[data-name=shareoption]");
            if (share_option) {
                share_option.classList.add("hidden");
                share_option.removeAttribute("data-name");
            }

            if (is_self_owned_share) {
                delete_btn.classList.remove("hidden");
                if (delete_btn.parentElement) {
                    delete_btn.parentElement.classList.remove("hidden");
                }
            } else {
                delete_btn.classList.add("hidden");
                if (delete_btn.parentElement) {
                    delete_btn.parentElement.classList.add("hidden");
                }
            }

            if (!is_incoming_share) {
                let has_write_properties = collection.has_permission(Permission.WRITE_PROPERTIES);
                if (has_write_properties) {
                    edit_btn.classList.remove("hidden");
                    if (edit_btn.parentElement) {
                        edit_btn.parentElement.classList.remove("hidden");
                    }
                } else {
                    edit_btn.classList.add("hidden");
                    if (edit_btn.parentElement) {
                        edit_btn.parentElement.classList.add("hidden");
                    }
                }
            }
        } else {
            share_control_enabled_li.classList.add("hidden");
            share_control_shown_li.classList.add("hidden");
            delete_btn.classList.remove("hidden");
            if (delete_btn.parentElement) {
                delete_btn.parentElement.classList.remove("hidden");
            }
            let has_write_properties = collection.has_permission(Permission.WRITE_PROPERTIES);
            if (has_write_properties) {
                edit_btn.classList.remove("hidden");
                if (edit_btn.parentElement) {
                    edit_btn.parentElement.classList.remove("hidden");
                }
            } else {
                edit_btn.classList.add("hidden");
                if (edit_btn.parentElement) {
                    edit_btn.parentElement.classList.add("hidden");
                }
            }
        }
        delete_btn.onclick = () => { return this._ondelete(collection, is_self_owned_share ? share : null); };
        edit_btn.onclick = () => { return this._onedit(collection); };
        share_btn.onclick = () => { return this._onshare(collection); };
        node.classList.remove("hidden");
        this._nodes.push(node);
        if (this._template.parentNode) {
            this._template.parentNode.insertBefore(node, this._template);
        }
    }

    /**
     * @param {Collection[]} collections
     * @param {import("../api/sharing.js").Share[]} shares
     * @param {boolean} clear_error
     */
    _show_collections(collections, shares, clear_error) {
        this._setup_layout();
        if (clear_error) {
            this._errorHandler.clearError();
        }

        let visible_collections = collections.filter((collection) => {
            let share = find_matching_map_share(collection.href, shares);
            if (share && share.Owner === this._user) {
                let conversion = (share.Conversion || "").toLowerCase();
                if (conversion === "none" || conversion === "") {
                    return false;
                }
            }
            return true;
        });

        let missing_incoming = get_missing_incoming_collections(visible_collections, shares, this._user);
        visible_collections.push(...missing_incoming);

        this._sort_collections(visible_collections, shares);
        this._clear_collections_display();

        visible_collections.forEach((collection) => {
            this._render_collection(collection, shares);
        });
    }

    _errorwrapper(/** @type {string} */ error) {
        this._errorHandler.setError(error);
        if (this._onerror) this._onerror(error);
    }

    show() {
        this._html_scene.classList.remove("hidden");
        this._new_btn.onclick = () => this._onnew();
        this._upload_btn.onclick = () => this._onupload();
        const mobileconfig_url = SERVER + ROOT_PATH + ".mobileconfig";
        this._mobileconfig_btn.href = mobileconfig_url;
        this._mobileconfig_btn.onclick = (event) => {
            event.preventDefault();
            this._download_file(mobileconfig_url, (this._user ? `${this._user}.mobileconfig` : "radicale.mobileconfig"));
        };
        collectionsCache.getChildCollections(this._user, this._password, this._principal_collection, (e) => this._errorwrapper(e), (c, s, ce) => this._show_collections(c, s, ce));
    }

    hide() {
        this._html_scene.classList.add("hidden");
        this._new_btn.onclick = null;
        this._upload_btn.onclick = null;
        if (this._mobileconfig_btn) {
            this._mobileconfig_btn.onclick = null;
        }
        this._clear_collections_display();
    }

    release() {
    }

    is_transient() { return false; }

    title_object() {
        if (this._principal_collection.displayname && this._principal_collection.displayname.length > 0)
            return this._principal_collection.displayname;
        else return this._user;
    }
}
