# nightsquirrel/bl_payer.py
from flask import Blueprint, render_template, redirect, request, flash, url_for, g
from flask_babel import gettext as _
from flask_login import login_required
import os

import logging
from .auth import manage_cookie_policy, payer_required
from .layoutUtils import set_menu, read_data_from_form
from .db_auth import (
    validate_sign_up, create_random_access_key, db_create_custom_name,
    db_create_custom_tile, db_create_user_entry, create_email_link_token,
    ext_send_email, db_get_user_by_email,
    db_set_user_as_payer, db_set_user_as_payer_only,
)
from .db_payment import (
    db_get_active_payer_link, db_create_payer_link,
    db_deactivate_payer_link, db_deactivate_payment_methods,
    db_create_payment_method,
    db_get_default_payment_method, db_update_payment_method_vault_id,
    db_update_vault_status, db_clear_vault,
)
from .paypal import create_vault_setup_token, create_payment_token, PayPalError
from .s3_operations import write_tile_to_s3

log = logging.getLogger(__name__)

bp = Blueprint('bl_payer', __name__, url_prefix='/payer')


@bp.route('/register', methods=('GET', 'POST'))
@login_required
@manage_cookie_policy
def register_payer():
    """Register a new payer (self-pay or new parent/guardian account)."""
    mc = set_menu("")

    if request.method == 'POST':
        form = read_data_from_form()
        is_self_pay = form.get('is_self_pay')  # checkbox -> True or absent

        if is_self_pay:
            # --- SELF-PAY FLOW ---
            paypal_email = (form.get('paypal_email') or '').strip()
            if not paypal_email:
                flash(_("PayPal email is required."), "warning")
                return render_template('payer/register_payer.html', mc=mc, form=form)

            db_create_payer_link(g.user_id, g.user_id, 'self')
            db_create_payment_method(g.user_id, paypal_email)
            db_set_user_as_payer(g.user_id)

            return redirect(url_for('bl_auth.userprofile', vault_prompt='self'))

        else:
            # --- NEW PAYER FLOW ---
            payer_email = (form.get('payer_email') or '').strip()
            relationship = form.get('relationship') or 'parent'
            paypal_email = (form.get('paypal_email') or '').strip()

            if not payer_email:
                flash(_("Payer email is required."), "warning")
                return render_template('payer/register_payer.html', mc=mc, form=form)
            if not paypal_email:
                flash(_("PayPal email is required."), "warning")
                return render_template('payer/register_payer.html', mc=mc, form=form)

            # Validate payer email format and uniqueness
            error = validate_sign_up({'email': payer_email})

            if error == 101:
                flash(_("Invalid payer email."), "warning")
                return render_template('payer/register_payer.html', mc=mc, form=form)

            if error == 102:
                # Payer email already belongs to an existing user -> link to them
                existing_payer = db_get_user_by_email(payer_email)
                if existing_payer:
                    payer_usr_id = existing_payer['usr_id']
                    db_create_payer_link(g.user_id, payer_usr_id, relationship)
                    db_create_payment_method(payer_usr_id, paypal_email)
                    db_set_user_as_payer(payer_usr_id)
                    next_url = request.args.get('next')
                    redirect_url = next_url or url_for('bl_auth.userprofile')
                    sep = '&' if '?' in redirect_url else '?'
                    redirect_url += f'{sep}vault_prompt=invited&payer_email={payer_email}'
                    return redirect(redirect_url)
                else:
                    flash(_("Could not find the payer account."), "danger")
                    return render_template('payer/register_payer.html', mc=mc, form=form)

            # error == 0: email is new -> create payer user account
            try:
                access_key = create_random_access_key()
                custom_name, custom_color = db_create_custom_name()
                tile_filename, tile_text = db_create_custom_tile(custom_color)
                payer_usr_id = db_create_user_entry(payer_email, access_key,
                                                    custom_name, tile_filename)

                # New payer: clear student flag, set payer flag
                db_set_user_as_payer_only(payer_usr_id)

                # Upload tile to S3
                write_tile_to_s3(tile_filename,
                                 os.environ["AWS_TILES_BUCKET_NAME"], tile_text)

                # Send credentials email to payer
                email_link_token = create_email_link_token(
                    payer_usr_id, payer_email, os.environ["JWT_SECRET_HTML"])
                ext_send_email(payer_email, access_key,
                               os.environ["BASE_URL"] + '/emailconfirmationhtml/',
                               'emailservice-ntsqr', 'signup',
                               email_link_token)

                # Create payer link and payment method
                db_create_payer_link(g.user_id, payer_usr_id, relationship)
                db_create_payment_method(payer_usr_id, paypal_email)

            except Exception as e:
                flash(_("Error creating payer account: %(error)s", error=str(e)), "danger")
                return render_template('payer/register_payer.html', mc=mc, form=form)

            next_url = request.args.get('next')
            redirect_url = next_url or url_for('bl_auth.userprofile')
            sep = '&' if '?' in redirect_url else '?'
            redirect_url += f'{sep}vault_prompt=invited&payer_email={payer_email}'
            return redirect(redirect_url)

    # If a payer link already exists, redirect to profile instead of showing a blank form
    payer_link = db_get_active_payer_link(g.user_id)
    if payer_link:
        pmt = db_get_default_payment_method(payer_link['payer_usr_id'])
        if not pmt or pmt.get('pmt_vault_status') != 'vaulted':
            if payer_link['payer_usr_id'] == g.user_id:
                flash(_("You already have a payment setup. Complete the PayPal connection below."), "info")
            else:
                flash(_("You already have a payer registered. They need to complete the PayPal setup from their own account."), "info")
        return redirect(url_for('bl_auth.userprofile'))

    return render_template('payer/register_payer.html', mc=mc, form={})


@bp.route('/unlink', methods=('POST',))
@login_required
@manage_cookie_policy
def unlink_payer():
    """Deactivate the current payer link and associated payment methods."""
    payer_link = db_get_active_payer_link(g.user_id)
    if payer_link:
        db_deactivate_payment_methods(payer_link['payer_usr_id'])
    ok = db_deactivate_payer_link(g.user_id)
    if ok:
        flash(_("Payment setup removed."), "info")
    else:
        flash(_("No active payer to unlink."), "warning")
    return redirect(url_for('bl_auth.userprofile'))


# ==================== VAULT ====================

@bp.route('/vault/setup', methods=('POST',))
@payer_required
@manage_cookie_policy
def vault_setup():
    """Start the PayPal vault setup flow -- redirect payer to PayPal."""
    return_url = url_for('bl_payer.vault_approve', _external=True)
    cancel_url = url_for('bl_payer.vault_cancel', _external=True)

    try:
        resp = create_vault_setup_token(return_url, cancel_url)
    except PayPalError as exc:
        log.exception("vault_setup: PayPal error")
        flash(_("Could not start PayPal setup: %(error)s", error=str(exc)), "danger")
        return redirect(url_for('bl_auth.userprofile'))

    # Mark vault status as pending_approval (payer is about to be redirected)
    pmt = db_get_default_payment_method(g.user_id)
    if pmt:
        db_update_vault_status(pmt["pmt_id"], "pending_approval")

    # Find the 'approve' link in the response
    approve_url = None
    for link in resp.get("links", []):
        if link.get("rel") == "approve":
            approve_url = link["href"]
            break

    if not approve_url:
        flash(_("PayPal did not return an approval link."), "danger")
        return redirect(url_for('bl_auth.userprofile'))

    return redirect(approve_url)


@bp.route('/vault/approve', methods=('GET',))
@payer_required
@manage_cookie_policy
def vault_approve():
    """PayPal redirects here after the payer approves the vault setup."""
    log.info("vault_approve query params: %s", dict(request.args))
    setup_token = request.args.get('approval_token_id') or request.args.get('vault_setup_token') or request.args.get('token_id')
    if not setup_token:
        flash(_("Missing vault setup token."), "warning")
        return redirect(url_for('bl_auth.userprofile'))

    try:
        resp = create_payment_token(setup_token)
    except PayPalError as exc:
        log.exception("vault_approve: PayPal error")
        flash(_("Could not finalize PayPal setup: %(error)s", error=str(exc)), "danger")
        return redirect(url_for('bl_auth.userprofile'))

    vault_id = resp.get("id")
    if not vault_id:
        flash(_("PayPal did not return a vault ID."), "danger")
        return redirect(url_for('bl_auth.userprofile'))

    # Store vault_id on the payer's default payment method
    pmt = db_get_default_payment_method(g.user_id)
    if pmt:
        db_update_payment_method_vault_id(pmt["pmt_id"], vault_id)

    flash(_("PayPal connected successfully."), "success")
    return redirect(url_for('bl_auth.userprofile'))


@bp.route('/vault/cancel', methods=('GET',))
@payer_required
@manage_cookie_policy
def vault_cancel():
    """PayPal redirects here if the payer cancels the vault setup."""
    flash(_("PayPal setup was cancelled."), "info")
    return redirect(url_for('bl_auth.userprofile'))


@bp.route('/vault/disconnect', methods=('POST',))
@payer_required
@manage_cookie_policy
def vault_disconnect():
    """Disconnect the payer's PayPal vault."""
    pmt = db_get_default_payment_method(g.user_id)
    if pmt:
        db_clear_vault(pmt["pmt_id"])
        flash(_("PayPal disconnected."), "info")
    else:
        flash(_("No payment method to disconnect."), "warning")
    return redirect(url_for('bl_auth.userprofile'))
