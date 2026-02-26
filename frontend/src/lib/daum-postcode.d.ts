interface DaumPostcodeData {
  zonecode: string;
  address: string;
  addressEnglish: string;
  addressType: string;
  userSelectedType: string;
  roadAddress: string;
  jibunAddress: string;
  buildingName: string;
  apartment: string;
  bname: string;
  bname1: string;
  bname2: string;
  sido: string;
  sigungu: string;
  query: string;
}

interface DaumPostcodeOptions {
  oncomplete: (data: DaumPostcodeData) => void;
  width?: string | number;
  height?: string | number;
}

interface DaumPostcode {
  new (options: DaumPostcodeOptions): { open: () => void; embed: (element: HTMLElement) => void };
}

interface Window {
  daum: {
    Postcode: DaumPostcode;
  };
}
