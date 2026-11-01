import React, { useState } from 'react';
import { Vendor, VendorCreate, VendorUpdate } from '../types/vendor';
import { createVendor, updateVendor } from '../services/vendorApi';
import { X, Building2, MapPin, Mail, Phone, Globe, CheckCircle2, AlertCircle } from 'lucide-react';

interface AddVendorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onVendorSaved: (vendor: Vendor) => void;
  initialVendor?: Vendor | null;
}

export const AddVendorModal: React.FC<AddVendorModalProps> = ({
  isOpen,
  onClose,
  onVendorSaved,
  initialVendor,
}) => {
  const isEditing = Boolean(initialVendor);

  const [businessName, setBusinessName] = useState(initialVendor?.business_name || '');
  const [vendorType, setVendorType] = useState(initialVendor?.vendor_type || 'Caterer');
  const [description, setDescription] = useState(initialVendor?.description || '');
  const [contactPerson, setContactPerson] = useState(initialVendor?.contact_person || '');
  const [email, setEmail] = useState(initialVendor?.email || '');
  const [phone, setPhone] = useState(initialVendor?.phone || '');
  const [websiteUrl, setWebsiteUrl] = useState(initialVendor?.website_url || '');
  const [city, setCity] = useState(initialVendor?.city || 'Mumbai');
  const [state, setState] = useState(initialVendor?.state || 'Maharashtra');
  const [address, setAddress] = useState(initialVendor?.address || '');
  const [verificationStatus, setVerificationStatus] = useState<any>(
    initialVendor?.verification_status || 'pending'
  );
  const [isActive, setIsActive] = useState<boolean>(initialVendor?.is_active ?? true);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!businessName.trim()) {
      setError('Business name is required.');
      return;
    }
    if (!vendorType.trim()) {
      setError('Vendor category / type is required.');
      return;
    }

    try {
      setIsSubmitting(true);
      if (isEditing && initialVendor) {
        const updatePayload: VendorUpdate = {
          business_name: businessName.trim(),
          vendor_type: vendorType.trim(),
          description: description.trim() || undefined,
          contact_person: contactPerson.trim() || undefined,
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
          website_url: websiteUrl.trim() || undefined,
          city: city.trim() || undefined,
          state: state.trim() || undefined,
          address: address.trim() || undefined,
          verification_status: verificationStatus,
          is_active: isActive,
        };
        const updated = await updateVendor(initialVendor.id, updatePayload);
        onVendorSaved(updated);
      } else {
        const createPayload: VendorCreate = {
          business_name: businessName.trim(),
          vendor_type: vendorType.trim(),
          description: description.trim() || undefined,
          contact_person: contactPerson.trim() || undefined,
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
          website_url: websiteUrl.trim() || undefined,
          city: city.trim() || undefined,
          state: state.trim() || undefined,
          address: address.trim() || undefined,
          verification_status: verificationStatus === 'verified' ? 'pending' : verificationStatus,
          is_active: isActive,
        };
        const created = await createVendor(createPayload);
        onVendorSaved(created);
      }
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to save vendor. Please check inputs.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-[#FFFDF9] border-2 border-black rounded-2xl shadow-[6px_6px_0px_0px_#000] overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-black bg-[#FFE600]">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-black stroke-[2.5]" />
            <h3 className="text-base font-black text-black uppercase tracking-tight font-heading">
              {isEditing ? 'Edit Vendor Profile' : 'Register New Vendor'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg border-2 border-black bg-white hover:bg-slate-100 transition-all text-black shadow-[1.5px_1.5px_0px_0px_#000]"
          >
            <X className="w-4 h-4 stroke-[3]" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-50 border-2 border-rose-600 text-rose-900 text-xs font-bold">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black">
                Business Name *
              </label>
              <input
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="e.g. Royal Banquet & Catering"
                required
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black">
                Primary Trade / Type *
              </label>
              <select
                value={vendorType}
                onChange={(e) => setVendorType(e.target.value)}
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              >
                <option value="Caterer">Caterer</option>
                <option value="Venue">Venue / Banquet</option>
                <option value="Decorator">Decorator / Florist</option>
                <option value="Photographer">Photographer / Videographer</option>
                <option value="AV & Production">AV, Sound & Lighting</option>
                <option value="Entertainment">Entertainment / DJ / Artist</option>
                <option value="Logistics">Logistics & Transportation</option>
                <option value="Other">Other Services</option>
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-black uppercase tracking-wider text-black">
              Profile Summary
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of specialties, capacity, and credentials"
              className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1">
                <MapPin className="w-3 h-3" /> City *
              </label>
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Mumbai, Pune"
                required
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black">
                State / Province
              </label>
              <input
                type="text"
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="Maharashtra"
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black">
                Contact Person
              </label>
              <input
                type="text"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                placeholder="Manager name"
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1">
                <Mail className="w-3 h-3" /> Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="contact@domain.com"
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1">
                <Phone className="w-3 h-3" /> Phone
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 98765 43210"
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1">
                <Globe className="w-3 h-3" /> Website / Portfolio
              </label>
              <input
                type="url"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t-2 border-black/10">
            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black">
                Verification State
              </label>
              <select
                value={verificationStatus}
                onChange={(e) => setVerificationStatus(e.target.value)}
                className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              >
                <option value="pending">Pending Verification</option>
                <option value="unverified">Unverified (Crowdsourced)</option>
                {isEditing && <option value="verified">Verified (Audited Credentials)</option>}
                {isEditing && <option value="rejected">Rejected</option>}
              </select>
              <span className="text-[10px] text-black/60 font-bold block">
                {isEditing
                  ? 'Verification status reflects manual auditor verification.'
                  : 'New registrations start as Pending or Unverified until authenticated.'}
              </span>
            </div>

            <div className="flex items-center gap-3 pt-4">
              <input
                type="checkbox"
                id="isActiveVendor"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="w-4 h-4 rounded border-2 border-black accent-[#FFE600]"
              />
              <label htmlFor="isActiveVendor" className="text-xs font-black text-black cursor-pointer">
                Listing Active in Directory
                <span className="text-[10px] text-black/60 font-bold block">
                  Inactive vendors are hidden from comparison and budget search.
                </span>
              </label>
            </div>
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t-2 border-black">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-black text-black bg-white hover:bg-slate-100 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-5 py-2 text-xs font-black text-black bg-[#FFE600] hover:bg-[#FFE600]/90 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
              <span>{isSubmitting ? 'Saving...' : isEditing ? 'Update Vendor' : 'Create Vendor'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

