--
-- Payment tables for payer model and PayPal integration (Phase 1)
--

-- ============================================================
-- TABLE: tbl_p_payer_link
-- Links a student to their payer (parent/guardian/self).
-- Only one active payer per student (enforced by partial unique index).
-- ============================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_p_payer_link (
  plk_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  student_usr_id  bigint NOT NULL,
  payer_usr_id    bigint NOT NULL,
  plk_relationship varchar(50) NOT NULL DEFAULT 'parent',
  plk_is_active   boolean NOT NULL DEFAULT true,
  plk_created_at  timestamptz NOT NULL DEFAULT now(),
  plk_updated_at  timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT chk_payer_link_relationship
    CHECK (plk_relationship IN ('parent', 'guardian', 'self', 'other'))
);

-- Only one ACTIVE payer per student
CREATE UNIQUE INDEX uq_payer_link_active_student
  ON nightsquirrel.tbl_p_payer_link (student_usr_id)
  WHERE plk_is_active = true;

ALTER TABLE nightsquirrel.tbl_p_payer_link
  ADD CONSTRAINT fk_payer_link_student
  FOREIGN KEY (student_usr_id)
  REFERENCES nightsquirrel.tbl_u_user (usr_id)
  ON DELETE CASCADE;

ALTER TABLE nightsquirrel.tbl_p_payer_link
  ADD CONSTRAINT fk_payer_link_payer
  FOREIGN KEY (payer_usr_id)
  REFERENCES nightsquirrel.tbl_u_user (usr_id)
  ON DELETE CASCADE;

CREATE INDEX idx_payer_link_student ON nightsquirrel.tbl_p_payer_link (student_usr_id);
CREATE INDEX idx_payer_link_payer   ON nightsquirrel.tbl_p_payer_link (payer_usr_id);


-- ============================================================
-- TABLE: tbl_p_payment_method
-- Payer's saved payment method (PayPal email for Phase 1,
-- vault token added in Phase 2 for automatic charging).
-- ============================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_p_payment_method (
  pmt_id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  payer_usr_id        bigint NOT NULL,
  pmt_type            varchar(20) NOT NULL DEFAULT 'paypal',
  pmt_paypal_email    varchar(255),
  pmt_paypal_vault_id varchar(255),
  -- Vault agreement lifecycle (PayPal Vault API v3):
  --   'none'             → method created, vault not yet attempted
  --   'pending_approval' → setup token created, payer redirected to PayPal
  --   'vaulted'          → payment token received, ready to charge
  --   'suspended'        → PayPal suspended the agreement (webhook)
  --   'cancelled'        → payer or merchant cancelled (webhook)
  --   'expired'          → agreement expired (webhook)
  pmt_vault_status    varchar(20) NOT NULL DEFAULT 'none',
  pmt_label           varchar(100),
  pmt_is_default      boolean NOT NULL DEFAULT true,
  pmt_is_active       boolean NOT NULL DEFAULT true,
  pmt_created_at      timestamptz NOT NULL DEFAULT now(),
  pmt_updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT chk_payment_method_type
    CHECK (pmt_type IN ('paypal')),
  CONSTRAINT chk_paypal_email_required
    CHECK (pmt_type <> 'paypal' OR pmt_paypal_email IS NOT NULL),
  CONSTRAINT chk_vault_status
    CHECK (pmt_vault_status IN ('none', 'pending_approval', 'vaulted',
                                'suspended', 'cancelled', 'expired'))
);

-- One default active method per payer
CREATE UNIQUE INDEX uq_payment_method_default_payer
  ON nightsquirrel.tbl_p_payment_method (payer_usr_id)
  WHERE pmt_is_default = true AND pmt_is_active = true;

ALTER TABLE nightsquirrel.tbl_p_payment_method
  ADD CONSTRAINT fk_payment_method_payer
  FOREIGN KEY (payer_usr_id)
  REFERENCES nightsquirrel.tbl_u_user (usr_id)
  ON DELETE CASCADE;

CREATE INDEX idx_payment_method_payer ON nightsquirrel.tbl_p_payment_method (payer_usr_id);


-- ============================================================
-- TABLE: tbl_p_payment
-- Transaction log: one record per charge attempt.
-- Schema created now; populated by business logic in Phase 2+.
-- ============================================================

CREATE TABLE IF NOT EXISTS nightsquirrel.tbl_p_payment (
  pay_id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tkt_id                bigint NOT NULL,
  payer_usr_id          bigint NOT NULL,
  pmt_id                bigint,
  pay_amount_cents      integer NOT NULL,
  pay_currency          char(3) NOT NULL DEFAULT 'EUR',
  -- Payment lifecycle (vault-based, no separate authorization step):
  --   'awaiting_charge' → record created when student accepts quote, charge
  --                        happens later when tutor delivers the answer
  --   'captured'        → PayPal charge successful (maps to PayPal capture COMPLETED)
  --   'failed'          → PayPal charge failed (maps to PayPal DECLINED/FAILED)
  --   'refunded'        → payment refunded after capture
  pay_status            varchar(20) NOT NULL DEFAULT 'awaiting_charge',
  pay_paypal_order_id   varchar(64),
  pay_paypal_capture_id varchar(64),
  pay_error_msg         text,
  pay_charged_at        timestamptz,
  pay_created_at        timestamptz NOT NULL DEFAULT now(),
  pay_updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT chk_payment_currency_len CHECK (char_length(pay_currency) = 3),
  CONSTRAINT chk_payment_amount_nonneg CHECK (pay_amount_cents >= 0),
  CONSTRAINT chk_payment_status
    CHECK (pay_status IN ('awaiting_charge', 'captured', 'failed', 'refunded'))
);

ALTER TABLE nightsquirrel.tbl_p_payment
  ADD CONSTRAINT fk_payment_ticket
  FOREIGN KEY (tkt_id)
  REFERENCES nightsquirrel.tbl_t_ticket (tkt_id)
  ON DELETE CASCADE;

ALTER TABLE nightsquirrel.tbl_p_payment
  ADD CONSTRAINT fk_payment_payer
  FOREIGN KEY (payer_usr_id)
  REFERENCES nightsquirrel.tbl_u_user (usr_id)
  ON DELETE RESTRICT;

ALTER TABLE nightsquirrel.tbl_p_payment
  ADD CONSTRAINT fk_payment_method
  FOREIGN KEY (pmt_id)
  REFERENCES nightsquirrel.tbl_p_payment_method (pmt_id)
  ON DELETE SET NULL;

CREATE INDEX idx_payment_ticket ON nightsquirrel.tbl_p_payment (tkt_id);
CREATE INDEX idx_payment_payer  ON nightsquirrel.tbl_p_payment (payer_usr_id);
CREATE INDEX idx_payment_status ON nightsquirrel.tbl_p_payment (pay_status);


-- ============================================================
-- TRIGGERS for updated_at columns
-- ============================================================

CREATE OR REPLACE FUNCTION nightsquirrel.fn_payer_link_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.plk_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payer_link_set_updated_at
BEFORE UPDATE ON nightsquirrel.tbl_p_payer_link
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_payer_link_set_updated_at();


CREATE OR REPLACE FUNCTION nightsquirrel.fn_payment_method_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.pmt_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payment_method_set_updated_at
BEFORE UPDATE ON nightsquirrel.tbl_p_payment_method
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_payment_method_set_updated_at();


CREATE OR REPLACE FUNCTION nightsquirrel.fn_payment_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.pay_updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payment_set_updated_at
BEFORE UPDATE ON nightsquirrel.tbl_p_payment
FOR EACH ROW
EXECUTE FUNCTION nightsquirrel.fn_payment_set_updated_at();
